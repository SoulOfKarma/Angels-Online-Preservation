"""Legacy quiz wire encoding, not used for passwords or transport security.

8074b0/8072b0/807400: standard Blowfish, first four ASCII key bytes.
807b20/807c80: independent blocks of two little-endian uint32s, zero padding.
5d53e0: six base64 fields separated by lIadQOdr.5d5fc0: encrypted appdata.
"""
import base64
import functools
from pathlib import Path
import struct

MASK=0xffffffff
SEPARATOR=b'lIadQOdr'


@functools.lru_cache(maxsize=1)
def _pi():
    text=(Path(__file__).parent/'plantillas/blowfish_pi.hex').read_text().strip()
    if len(text)!=1042*8:raise ValueError('Invalid Blowfish table')
    return tuple(int(text[i:i+8],16) for i in range(0,len(text),8))


class Cipher:
    def __init__(self,key):
        if isinstance(key,str):key=key.encode('ascii')
        if len(key)<4:raise ValueError('Quiz key must have four bytes')
        key=key[:4]
        self.words=list(_pi())
        for i in range(18):self.words[i]^=int.from_bytes(key,'big')
        l=r=0
        for i in range(0,1042,2):
            l,r=self.block(l,r)
            self.words[i:i+2]=l,r

    def _f(self,x):
        w=self.words
        return (((w[18+(x>>24)]+w[274+((x>>16)&255)])&MASK)^w[530+((x>>8)&255)])+w[786+(x&255)]&MASK

    def block(self,l,r,decrypt=False):
        p=self.words
        for i in (range(17,1,-1) if decrypt else range(16)):
            l^=p[i];r^=self._f(l);l,r=r,l
        l,r=r,l
        r^=p[1 if decrypt else 16];l^=p[0 if decrypt else 17]
        return l,r

    def encode(self,text):
        raw=text.encode('latin-1','replace') if isinstance(text,str) else bytes(text)
        raw+=bytes((-len(raw))%8)
        return base64.b64encode(b''.join(struct.pack('<II',*self.block(*struct.unpack_from('<II',raw,i)))
                                       for i in range(0,len(raw),8)))

    def decode(self,encoded):
        raw=base64.b64decode(encoded,validate=True)
        if not raw or len(raw)%8 or len(raw)>512:raise ValueError('Invalid quiz ciphertext')
        data=b''.join(struct.pack('<II',*self.block(*struct.unpack_from('<II',raw,i),decrypt=True))
                      for i in range(0,len(raw),8))
        return data.split(b'\0',1)[0].decode('latin-1')


def question(cipher,row,answers,seed):
    #Native snprintf treats the decoded XML as a format string twice for
    #answers. Escape percent signs so questions cannot become printf input.
    fields=[row['text'][:240],*(a[:100] for a in answers),row['category'][:60],str(seed)]
    encoded=[cipher.encode(v.replace('%','%%%%') if i in (1,2,3) else v.replace('%','%%'))
             for i,v in enumerate(fields)]
    if any(SEPARATOR in v for v in encoded):raise ValueError('Quiz field contains separator')
    return SEPARATOR.join(encoded)+b'\0'


def answer(cipher,encoded,seed):
    text=cipher.decode(encoded)
    if not text.isascii() or not text.isdecimal():raise ValueError('Invalid encoded answer')
    value=int(text)
    if not 0<=value<=MASK or value&((1<<seed)-1):raise ValueError('Invalid encoded answer')
    result=(value>>seed)-seed
    if result not in (0,1,2):raise ValueError('Invalid answer')
    return result
