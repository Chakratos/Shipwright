#!/usr/bin/env python3
"""Bounded MIPS32/COP1 execution of exact original owner-ROM game code.

No reconstructed fake animation or uploaded source instructions.
This is a real CPU instruction interpreter; successful execution is not
proof of correct animation until live render globals are validated.
"""
from __future__ import annotations
from collections import Counter
import struct

STOP=0xF0000000
U32=0xFFFFFFFF

def s16(x):
    x &= 65535
    return x-65536 if x&32768 else x

def s32(x):
    x &= U32
    return x-4294967296 if x&0x80000000 else x

def f32(bits):
    return struct.unpack(">f",struct.pack(">I",bits&U32))[0]

def bits32(value):
    return struct.unpack(">I",struct.pack(">f",value))[0]

class MipsFault(ValueError):
    pass

class OriginalMipsCPU:
    def __init__(self,ram_size=8*1024*1024):
        self.ram=bytearray(ram_size)
        self.r=[0]*32
        self.f=[0]*32
        self.hi=self.lo=0
        self.fcond=False
        self.pc=0
        self.executed=0
        self.calls=Counter()
        self.first_calls=[]
        self.reads=Counter()
        self.writes=Counter()
        self.visited=set()
        self.source_region=(0,0)

    def at(self,address,size,align=1):
        address&=U32
        if address%align:
            raise MipsFault(f"unaligned memory 0x{address:08X}")
        if not (0x80000000<=address<0xC0000000):
            raise MipsFault(f"unmapped virtual memory 0x{address:08X}")
        physical=address&0x1FFFFFFF
        if physical+size>len(self.ram):
            raise MipsFault(f"unmapped RDRAM 0x{address:08X}")
        return physical

    def load(self,address,size=4):
        off=self.at(address,size,size)
        return int.from_bytes(self.ram[off:off+size],"big")

    def store(self,address,value,size=4):
        off=self.at(address,size,size)
        self.ram[off:off+size]=(value&((1<<(size*8))-1)).to_bytes(size,"big")

    def copy(self,address,data):
        off=self.at(address,len(data))
        self.ram[off:off+len(data)]=data

    def put_float(self,address,value):
        self.store(address,bits32(value))

    def write(self,reg,value):
        if reg:
            self.r[reg]=value&U32

    def region(self,address):
        lo,hi=self.source_region
        if lo<=address<hi and hi>lo:return "source_07"
        if 0x80168400<=address<0x80168600:return "animation_globals"
        if 0x807F0000<=address<0x80800000:return "stack"
        if 0x80600000<=address<0x80601000:return "object"
        return "other"

    def instruction(self,pc,*,delay=False):
        w=self.load(pc)
        op=w>>26
        rs=(w>>21)&31
        rt=(w>>16)&31
        rd=(w>>11)&31
        sh=(w>>6)&31
        fn=w&63
        imm=w&65535
        a,b=self.r[rs],self.r[rt]
        self.executed+=1
        self.visited.add(pc)
        jump=None

        if op==0:
            if fn==0:self.write(rd,b<<sh)
            elif fn==2:self.write(rd,b>>sh)
            elif fn==3:self.write(rd,s32(b)>>sh)
            elif fn==4:self.write(rd,b<<(a&31))
            elif fn==6:self.write(rd,b>>(a&31))
            elif fn==7:self.write(rd,s32(b)>>(a&31))
            elif fn in (8,9):
                if fn==9:
                    self.write(rd or 31,pc+8)
                    self.calls[f"0x{a:08X}"]+=1
                    if len(self.first_calls)<16:
                        self.first_calls.append({"target":f"0x{a:08X}", "args":[f"0x{self.r[n]:08X}" for n in range(4,8)]})
                jump=(True,a,False)
            elif fn in (0x20,0x21):self.write(rd,a+b)
            elif fn in (0x22,0x23):self.write(rd,a-b)
            elif fn==0x24:self.write(rd,a&b)
            elif fn==0x25:self.write(rd,a|b)
            elif fn==0x26:self.write(rd,a^b)
            elif fn==0x27:self.write(rd,~(a|b))
            elif fn==0x2A:self.write(rd,int(s32(a)<s32(b)))
            elif fn==0x2B:self.write(rd,int(a<b))
            elif fn in (0x18,0x19):
                value=s32(a)*s32(b) if fn==0x18 else a*b
                self.lo=value&U32
                self.hi=(value>>32)&U32
            elif fn in (0x1A,0x1B):
                numerator=s32(a) if fn==0x1A else a
                denominator=s32(b) if fn==0x1A else b
                if denominator:
                    q=abs(numerator)//abs(denominator)
                    if (numerator<0)!=(denominator<0):q=-q
                    self.lo=q&U32
                    self.hi=(numerator-q*denominator)&U32
            elif fn==0x10:self.write(rd,self.hi)
            elif fn==0x12:self.write(rd,self.lo)
            else:raise MipsFault(f"unknown R instruction 0x{fn:02X} at 0x{pc:08X}")
        elif op in (2,3):
            target=((pc+4)&0xF0000000)|((w&0x03FFFFFF)<<2)
            if op==3:
                self.write(31,pc+8)
                self.calls[f"0x{target:08X}"]+=1
                if len(self.first_calls)<16:
                    self.first_calls.append({"target":f"0x{target:08X}", "args":[f"0x{self.r[n]:08X}" for n in range(4,8)]})
            jump=(True,target,False)
        elif op in (4,5,6,7,0x14,0x15,0x16,0x17):
            taken={4:a==b,5:a!=b,6:s32(a)<=0,7:s32(a)>0,
                   0x14:a==b,0x15:a!=b,0x16:s32(a)<=0,0x17:s32(a)>0}[op]
            jump=(taken,(pc+4+s16(imm)*4)&U32,op>=0x14)
        elif op==1:
            if rt not in (0,1,2,3,16,17,18,19):
                raise MipsFault(f"unknown REGIMM at 0x{pc:08X}")
            taken=s32(a)<0 if rt in (0,2,16,18) else s32(a)>=0
            if taken and rt in (16,17,18,19):self.write(31,pc+8)
            jump=(taken,(pc+4+s16(imm)*4)&U32,rt in (2,3,18,19))
        elif op==15:self.write(rt,imm<<16)
        elif op in (8,9):self.write(rt,a+s16(imm))
        elif op==12:self.write(rt,a&imm)
        elif op==13:self.write(rt,a|imm)
        elif op==14:self.write(rt,a^imm)
        elif op==10:self.write(rt,int(s32(a)<s16(imm)))
        elif op==11:self.write(rt,int(a<(s16(imm)&U32)))
        elif op in (0x20,0x21,0x23,0x24,0x25,0x28,0x29,0x2B,0x31,0x39):
            address=(a+s16(imm))&U32
            width=(1 if op in (0x20,0x24,0x28) else
                   2 if op in (0x21,0x25,0x29) else 4)
            label=self.region(address)
            if op in (0x20,0x21,0x23,0x24,0x25,0x31):
                self.reads[label]+=1
                try:
                    val=self.load(address,width)
                except MipsFault as fault:
                    raise MipsFault(f"{fault}; original PC=0x{pc:08X} op=0x{op:02X} base=r{rs}=0x{a:08X} imm={s16(imm)}") from fault
                if op in (0x20,0x21) and val&(1<<(width*8-1)):
                    val-=1<<(width*8)
                if op==0x31:self.f[rt]=val&U32
                else:self.write(rt,val)
            else:
                self.writes[label]+=1
                try:
                    self.store(address,self.f[rt] if op==0x39 else b,width)
                except MipsFault as fault:
                    raise MipsFault(f"{fault}; original PC=0x{pc:08X} op=0x{op:02X} base=r{rs}=0x{a:08X} imm={s16(imm)}") from fault
        elif op==0x11:
            fmt=rs
            fs=(w>>11)&31
            fd=(w>>6)&31
            if fmt==0:self.write(rt,self.f[fs])
            elif fmt==4:self.f[fs]=b
            elif fmt==8:
                taken=self.fcond if rt&1 else not self.fcond
                jump=(taken,(pc+4+s16(imm)*4)&U32,bool(rt&2))
            elif fmt==16:
                x,y=f32(self.f[fs]),f32(self.f[rt])
                if fn in (0,1,2,3,5,6,7):
                    if fn==0:out=x+y
                    elif fn==1:out=x-y
                    elif fn==2:out=x*y
                    elif fn==3:
                        if y==0:raise MipsFault("original FPU divide by zero")
                        out=x/y
                    elif fn==5:out=abs(x)
                    elif fn==6:
                        self.f[fd]=self.f[fs]
                        return jump
                    else:out=-x
                    self.f[fd]=bits32(out)
                elif fn==0x24:self.f[fd]=int(round(x))&U32
                elif fn in (0x32,0x3C,0x3E):
                    self.fcond={0x32:x==y,0x3C:x<y,0x3E:x<=y}[fn]
                else:raise MipsFault(f"unknown COP1.S fn 0x{fn:02X} at 0x{pc:08X}")
            elif fmt==20 and fn==0x20:self.f[fd]=bits32(float(s32(self.f[fs])))
            else:raise MipsFault(f"unknown COP1 format 0x{fmt:02X} at 0x{pc:08X}")
        else:raise MipsFault(f"unknown MIPS opcode 0x{op:02X} at 0x{pc:08X}")
        if delay and jump is not None:
            raise MipsFault(f"nested original branch delay at 0x{pc:08X}")
        return jump

    def run(self,entry,*,budget=200000):
        if budget<1 or budget>1000000:raise MipsFault("invalid budget")
        self.pc=entry
        self.r[29]=0x807FE000
        self.r[31]=STOP
        while self.pc!=STOP:
            if self.executed>=budget:raise MipsFault("MIPS original instruction budget exceeded")
            pc=self.pc
            transfer=self.instruction(pc)
            if transfer is None:
                self.pc=(pc+4)&U32
                continue
            taken,target,likely=transfer
            if taken or not likely:
                if self.executed>=budget:raise MipsFault("delay slot instruction budget exceeded")
                self.instruction((pc+4)&U32,delay=True)
            self.pc=target if taken else (pc+8)&U32
        return {
            "returned":True,
            "executed":self.executed,
            "distinct_instructions":len(self.visited),
            "calls":dict(sorted(self.calls.items())),
            "read_regions":dict(self.reads),
            "write_regions":dict(self.writes),
            "verified_animation_pose":False,
        }
