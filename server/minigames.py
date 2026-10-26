"""Native C2S0010/S2C001f social games and original access cards.

749a70 is the submessage envelope.5f1840 opens each game; the virtual
receivers4f3050/4f4540/4f6290/4f9460 consume its game-specific messages.
Only the host needs a card. Games award virtual scores, never currency.
"""
import dataclasses
import itertools
import random
import struct
import time

import minigame_rules as rules

_GAMES={}
_PENDING={}
_IDS=itertools.count(1)
NAMES={1:'5 in a row',2:'Bingo',3:'Big-2',4:'Othello'}
_DYNAMIC_TO_GAME=(1,3,2,4)
_VOUCHERS={**{494+i:1377+i for i in range(4)},**{2004+i:2973+i for i in range(12)}}
_HIDDEN=set(_VOUCHERS.values())


def _key(s):return s.usuario.casefold(),s.personaje.char_id
def _live(s):return getattr(s,'personaje',None) is not None and not getattr(s,'desconectado',False)
def _notice(s,text):
    import clases
    s.enviar(clases.aviso(text,tipo=0))
def _packet(sub,body=b''):return struct.pack('<HH',0x1f,sub)+body


def card(item):
    hidden=_VOUCHERS.get(item,item if item in _HIDDEN else None)
    if hidden is None:return None
    from album import _items
    row=_items()[hidden]
    dynamic=int(row.get('\u52d5\u614b\u8cc7\u65991') or 0)
    return hidden,156+dynamic,_DYNAMIC_TO_GAME[dynamic],int(row.get('\u6301\u7e8c\u6642\u9593') or 0)*60


def usar(s,slot):
    item=s.inventario.get(slot);info=card(item)
    if info is None:return False
    import recent_mall
    hidden,dest,kind,seconds=info
    if not 20<=slot<156:return True
    deadline=time.time()+seconds if seconds else 0
    def activate(con,data):
        old=data['inventario'].get(str(dest))
        previous=(data.get('mejoras') or {}).get(str(dest),{}).get('mini_game_fin',0)
        if old and (not previous or previous>=deadline and deadline):
            raise recent_mall.Rechazo('You already have this game card with an equal or longer duration.')
        data['inventario'][str(dest)]=hidden;data['cantidades'][str(dest)]=1
        data.setdefault('mejoras',{})[str(dest)]=({'mini_game_fin':deadline,'mall_fin':deadline,'mall_item':hidden} if deadline else {})
    try:recent_mall.cambiar(s,{slot:1},[],transaccion=activate)
    except recent_mall.Rechazo as exc:_notice(s,str(exc));return True
    _notice(s,'%s is now available in your Friends Game menu%s.'%(NAMES[kind],' permanently' if not seconds else ' for%d days'%(seconds//86400)))
    return True


def _access(s,kind):
    for slot,item in s.inventario.items():
        info=card(item)
        if info and info[1]==slot and info[2]==kind:
            deadline=(s.personaje.mejoras or {}).get(slot,{}).get('mini_game_fin',0)
            if not deadline or deadline>time.time():return True
    return False


@dataclasses.dataclass
class Game:
    ident:int
    kind:int
    players:list
    identities:list
    ready:set=dataclasses.field(default_factory=set)
    transcript:list=dataclasses.field(default_factory=list)
    state:str='lobby'
    turn:int=0
    board:dict=dataclasses.field(default_factory=dict)
    bingo:dict=dataclasses.field(default_factory=dict)
    called:set=dataclasses.field(default_factory=set)
    hands:list=dataclasses.field(default_factory=list)
    previous:list=dataclasses.field(default_factory=list)
    passes:int=0
    leader:int=0


def _game(s):
    return next((g for g in _GAMES.values() if any(p is s and original is s.personaje
                 for p,original in zip(g.players,g.identities))),None)
def _send(g,packet):
    g.transcript.append((None,packet))
    for s in g.players:
        if _live(s):s.enviar(packet)


def _private(g,s,packet):
    g.transcript.append((_key(s),packet));s.enviar(packet)


def loaded(s):
    _prune();g=_game(s)
    if not g:return
    records=b''.join(struct.pack('<I17s',p.personaje.char_id,p.personaje.nombre.encode('latin1','replace')[:16].ljust(17,b'\0')) for p in g.players)
    s.enviar(_packet(3,struct.pack('<IIIH',g.ident,s.personaje.char_id,len(g.players),g.kind)+records))
    for target,packet in g.transcript:
        if target is None or target==_key(s):s.enviar(packet)
def _open(g):
    records=b''.join(struct.pack('<I17s',s.personaje.char_id,s.personaje.nombre.encode('latin-1','replace')[:16].ljust(17,b'\0')) for s in g.players)
    for s in g.players:
        s.enviar(_packet(3,struct.pack('<IIIH',g.ident,s.personaje.char_id,len(g.players),g.kind)+records))


def _close(g):
    _send(g,_packet(4));_GAMES.pop(g.ident,None)
def desconectar(s):
    for key,pending in list(_PENDING.items()):
        if pending[0] is s or pending[1] is s:_PENDING.pop(key,None)
    g=_game(s)
    if g:_close(g)
def _prune():
    for g in list(_GAMES.values()):
        if any(not _live(s) or s.personaje is not original for s,original in zip(g.players,g.identities)):_close(g)
    for key,invite in list(_PENDING.items()):
        if invite[3]<time.time() or not _live(invite[0]) or not _live(invite[1]):_PENDING.pop(key,None)


def _start(g):
    g.transcript.clear()
    g.state='playing';g.turn=0;g.board={};g.called=set();g.previous=[];g.passes=0
    if g.kind==1:
        _send(g,_packet(0x15));_send(g,_packet(0x16))
    elif g.kind==2:
        g.state='selecting';g.bingo={};_send(g,_packet(0x1f))
    elif g.kind==4:
        g.board={(3,3):1,(4,4):1,(3,4):2,(4,3):2}
        _send(g,_packet(0x23,struct.pack('<I',1)))
    else:
        deck=random.sample(range(52),52)
        #The native first-play UI specifically expects3-diamonds(41).
        pos=deck.index(41)
        if pos>=13*len(g.players):
            destination=random.randrange(13*len(g.players))
            deck[destination],deck[pos]=deck[pos],deck[destination]
        g.hands=[set(deck[i*13:(i+1)*13]) for i in range(len(g.players))]
        g.turn=g.leader=next(i for i,hand in enumerate(g.hands) if 41 in hand)
        _send(g,_packet(0x19,struct.pack('<4i',0,0,0,0)))
        for s,hand in zip(g.players,g.hands):_private(g,s,_packet(0x1a,struct.pack('<I13i',g.turn,*sorted(hand,key=rules.card_rank))))


def _finish(g,winner,forfeit=False):
    g.state='finished';g.ready.clear()
    if g.kind==1:
        ident=g.players[winner].personaje.char_id if winner is not None else 0
        _send(g,_packet(0x17,struct.pack('<III',ident,0,0)))
    elif g.kind in (2,4):
        sub=0x22 if g.kind==2 else 0x26
        body=bytearray(25)
        struct.pack_into('<I',body,0,3 if winner is None else winner+1)
        if g.kind==2:
            counts=[_bingo_lines(g,i) for i in range(2)]
        else:counts=[sum(n==i+1 for n in g.board.values()) for i in range(2)]
        if g.kind==4:struct.pack_into('<II',body,16,*counts);body[24]=int(forfeit)
        _send(g,_packet(sub,bytes(body)))
    else:
        points=[-len(hand) for hand in g.hands]
        if winner is not None:points[winner]=-sum(points[i] for i in range(len(points)) if i!=winner)
        _send(g,_packet(0x1c,struct.pack('<4i',*(points+[0]*(4-len(points))))))
    result='Draw.' if winner is None else '%s wins.'%g.players[winner].personaje.nombre
    for s in g.players:_notice(s,'%s: %s'%(NAMES[g.kind],result))


def _bingo_lines(g,player):
    board=g.bingo.get(player,[])
    return rules.lines({(i%5,i//5) for i,n in enumerate(board) if n in g.called})


def _move(g,s,sub,raw):
    index=next(i for i,p in enumerate(g.players) if p is s)
    if g.kind==2 and sub==30 and g.state=='selecting':
        if len(raw)!=100 or index in g.bingo:return
        numbers=list(struct.unpack('<25I',raw))
        if sorted(numbers)!=list(range(1,26)):return
        g.bingo[index]=numbers
        if len(g.bingo)==len(g.players):
            g.state='playing';_send(g,_packet(0x20,struct.pack('<I',g.players[0].personaje.char_id)))
        return
    if g.state!='playing':return
    if (g.kind==1 and sub==21) or (g.kind==4 and sub==34):
        _finish(g,1-index,True);return
    if index!=g.turn:return
    if g.kind==1 and sub==20 and len(raw)==8:
        x,y=struct.unpack('<II',raw)
        if not 0<=x<15 or not 0<=y<15 or (x,y) in g.board:return
        g.board[x,y]=index+1;g.turn=1-index
        _send(g,_packet(0x14,struct.pack('<4I',s.personaje.char_id,x*16,y*16,len(g.board))))
        if rules.five(g.board,x,y,index+1):_finish(g,index)
        elif len(g.board)==225:_finish(g,None)
    elif g.kind==2 and sub==31 and len(raw)==8:
        number,cell=struct.unpack('<II',raw)
        if number in g.called or not 1<=number<=25 or not 0<=cell<25 or g.bingo[index][cell]!=number:return
        g.called.add(number);g.turn=1-index
        counts=[_bingo_lines(g,i) for i in range(2)]
        _send(g,_packet(0x21,struct.pack('<4I',g.players[g.turn].personaje.char_id,number,*counts)))
        winners=[i for i,n in enumerate(counts) if n>=5]
        if winners:_finish(g,winners[0] if len(winners)==1 else None)
    elif g.kind==4 and sub==32 and len(raw)==9:
        x,y,passing=struct.unpack('<IIB',raw)
        if passing:
            if rules.legal_moves(g.board,index+1):return
        else:
            flipped=rules.flips(g.board,x,y,index+1)
            if not flipped:return
            g.board[x,y]=index+1
            for tile in flipped:g.board[tile]=index+1
        g.turn=1-index
        body=struct.pack('<4I2B',g.turn+1,x,y,0,int(not rules.legal_moves(g.board,g.turn+1)),int(bool(passing)))
        _send(g,_packet(0x24,body))
        if not rules.legal_moves(g.board,1) and not rules.legal_moves(g.board,2):
            counts=[sum(n==side for n in g.board.values()) for side in (1,2)]
            _finish(g,0 if counts[0]>counts[1] else 1 if counts[1]>counts[0] else None)
    elif g.kind==3 and ((sub==25 and len(raw)==25) or (sub==26 and not raw)):
        cards=[] if sub==26 else [c for c in struct.unpack_from('<5i',raw,5) if c!=-1]
        reset=False
        if not cards:
            if not g.previous or g.leader==index:return
            g.passes+=1
            if g.passes==len(g.players)-1:reset=True;g.previous=[];g.passes=0
            kind=0
        else:
            if not set(cards)<=g.hands[index] or not rules.beats(cards,g.previous):return
            if all(len(h)==13 for h in g.hands) and 41 not in cards:return
            cards.sort(key=lambda c:(c%13,c//13))
            kind=rules.combination(cards)[0]
            g.hands[index].difference_update(cards);g.previous=list(cards);g.leader=index;g.passes=0
        g.turn=(index+1)%len(g.players)
        if reset:g.turn=g.leader
        won=bool(cards) and not g.hands[index]
        #27 uses turn number1..N after a play. For a pass the native UI also
        #expects next turn; sending kind0 avoids trusting any client cards.
        body=struct.pack('<BBII5i',int(won),int(reset),index+1,kind,*(cards+[-1]*(5-len(cards))))
        _send(g,_packet(0x1b,body))
        if won:_finish(g,index)


def procesar(s,body,sessions):
    if not _live(s) or len(body)<2:return
    _prune();sub=struct.unpack_from('<H',body)[0];raw=body[2:]
    if sub==0:
        if len(raw)!=19:return
        kind=struct.unpack_from('<H',raw)[0]
        if kind not in NAMES or not _access(s,kind):
            _notice(s,'Activate the corresponding game card before inviting another player.');return
        name=raw[2:].split(b'\0',1)[0].decode('latin-1')
        target=next((p for p in sessions if _live(p) and p is not s and p.personaje.nombre.casefold()==name.casefold()),None)
        existing=_game(s)
        can_expand=(existing is not None and kind==3 and existing.kind==3
                    and existing.players[0] is s and existing.state=='lobby' and len(existing.players)<4)
        if target is None or _game(target) or (existing is not None and not can_expand):
            _notice(s,'That player is unavailable for a game.');return
        import chatrooms
        if chatrooms._blocked(s,target):return
        if _key(target) in _PENDING:return
        _PENDING[_key(target)]=(s,target,kind,time.time()+60,s.personaje,target.personaje,existing.ident if existing else None)
        target.enviar(_packet(0,struct.pack('<I17sHI',s.personaje.char_id,s.personaje.nombre.encode('latin-1','replace')[:16].ljust(17,b'\0'),kind,60000)))
        return
    if sub==1:
        if len(raw)!=5:return
        source,accept=struct.unpack('<IB',raw)
        invite=_PENDING.get(_key(s))
        if not invite or invite[0].personaje is not invite[4] or s.personaje is not invite[5] or source!=invite[0].personaje.char_id:return
        _PENDING.pop(_key(s),None)
        host,_,kind,*_=invite
        if accept!=1 or _game(s) or not _access(host,kind):return
        import chatrooms
        if chatrooms._blocked(host,s) or chatrooms._blocked(s,host):return
        g=_game(host)
        if g is not None:
            if invite[6]!=g.ident or kind!=3 or g.kind!=3 or g.players[0] is not host or g.state!='lobby' or len(g.players)>=4:return
            g.players.append(s);g.identities.append(s.personaje);g.ready.clear()
        else:
            if invite[6] is not None:return
            g=Game(next(_IDS),kind,[host,s],[host.personaje,s.personaje]);_GAMES[g.ident]=g
        _open(g)
        return
    g=_game(s)
    if g is None:return
    if sub==2 and not raw:
        if not getattr(s,'mapa_cargando',False):_close(g)
        return
    if sub==3 and len(raw)==4 and g.state in ('lobby','finished'):
        g.ready.add(_key(s))
        if len(g.ready)==len(g.players):g.ready.clear();_start(g)
        return
    _move(g,s,sub,raw)
