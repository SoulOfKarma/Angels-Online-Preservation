"""Authoritative board and card rules for the native social minigames."""
from collections import Counter


def lines(cells,size=5):
    groups=[[(x,y) for x in range(size)] for y in range(size)]
    groups += [[(x,y) for y in range(size)] for x in range(size)]
    groups += [[(i,i) for i in range(size)],[(i,size-1-i) for i in range(size)]]
    return sum(all(p in cells for p in group) for group in groups)


def five(board,x,y,side):
    for dx,dy in ((1,0),(0,1),(1,1),(1,-1)):
        count=1
        for sign in (-1,1):
            nx,ny=x+dx*sign,y+dy*sign
            while board.get((nx,ny))==side:
                count+=1;nx+=dx*sign;ny+=dy*sign
        if count>=5:return True
    return False


def flips(board,x,y,side):
    if not 0<=x<8 or not 0<=y<8 or (x,y) in board:return []
    result=[]
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
        line=[];nx,ny=x+dx,y+dy
        while 0<=nx<8 and 0<=ny<8 and board.get((nx,ny))==3-side:
            line.append((nx,ny));nx+=dx;ny+=dy
        if line and board.get((nx,ny))==side:result+=line
    return result


def legal_moves(board,side):
    return [(x,y) for x in range(8) for y in range(8) if flips(board,x,y,side)]


def card_rank(card):
    #Native deck:suit*13 +rank(A=0,2=1,3=2,...K=12). 41 is3-diamonds.
    return (card%13-2)%13,3-card//13


def combination(cards):
    """Native4f6c90/4f7230: singles,pairs,straights,houses,quads,straight flushes.

    A flush alone is not a valid play in this client.23456 is the highest
    straight,followed by10JQKA;A2345 is a low ordinary straight.
    """
    if len(set(cards))!=len(cards) or any(not 0<=c<52 for c in cards):return None
    ordered=sorted(cards,key=card_rank);counts=Counter(c%13 for c in cards)
    if len(cards)==1:return 1,card_rank(cards[0])
    if len(cards)==2:
        return (2,max(card_rank(c) for c in cards)) if len(counts)==1 else None
    if len(cards)!=5:return None
    ranks=sorted(counts)
    flush=len({c//13 for c in cards})==1
    straight=len(ranks)==5 and (ranks==list(range(ranks[0],ranks[0]+5)) or ranks==[0,9,10,11,12])
    if straight:
        if ranks[0]==1:key=(2,3-min(c//13 for c in cards if c%13==1))
        elif ranks==[0,9,10,11,12]:key=(1,3-min(c//13 for c in cards if c%13==0))
        else:key=(0,ranks[-1],3-min(c//13 for c in cards if c%13==ranks[-1]))
        return (6 if flush else 3),key
    if 4 in counts.values():return 5,((next(r for r,n in counts.items() if n==4)-2)%13,)
    if sorted(counts.values())==[2,3]:return 4,((next(r for r,n in counts.items() if n==3)-2)%13,)
    return None


def beats(cards,previous):
    current=combination(cards);old=combination(previous)
    if not current:return False
    if not previous:return True
    if not old:return False
    if current[0]==old[0]:return current[1]>old[1]
    return current[0]==6 or (current[0]==5 and old[0]!=6)
