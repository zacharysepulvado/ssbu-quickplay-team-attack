#!/usr/bin/env python3
"""Execute release AArch64 callbacks in Unicorn, using a Skyline-style handler.

Needs pyelftools, unicorn and keystone-engine. This checks compiled callback
behavior and register/memory preservation, not the installed Switch loader or
live game lifecycle. The only permitted external call is a deterministic tick.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ
from unicorn.arm64_const import *
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

P=0x10000000; G=0x7100000000; S=0x20000000; ST=0x30000000; H=0x11000000; END=H+0x2000; R=0x21000000
X=[UC_ARM64_REG_X0+i for i in range(29)]+[UC_ARM64_REG_X29,UC_ARM64_REG_X30]
NAMES=['local','participant','ready','before','after','submit','receive','stored']
MOVS=['mov w8, #0x3738','mov w8, #0x3738','mov w8, #1','mov w8, #0x4638','mov w8, #0x46ac','mov w23, w4','mov w10, #0x1350','mov w11, #0x16b8']
TICK=19200*250+123

def run(elf_path):
    with open(elf_path,'rb') as f:
        elf=ELFFile(f)
        segs=[(s['p_vaddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
        symbols=list(elf.get_section_by_name('.symtab').iter_symbols())
        def symbol(tail):
            matches=[s['st_value'] for s in symbols if 'application_probe' in s.name and s.name.endswith(tail)]
            assert len(matches)==1,(tail,matches)
            return P+matches[0]
        relocs=[]
        externals={}
        for section in elf.iter_sections():
            if section['sh_type']!='SHT_RELA':continue
            table=elf.get_section(section['sh_link'])
            for r in section.iter_relocations():
                t=r['r_info_type']; sym=table.get_symbol(r['r_info_sym'])
                if t==1027: v=P+r['r_addend']
                elif t in (257,1025,1026):
                    if sym['st_shndx']!='SHN_UNDEF':v=P+sym['st_value']+r['r_addend']
                    else:
                        if sym.name not in externals:externals[sym.name]=H+0x3000+len(externals)*16
                        v=externals[sym.name]
                else:raise AssertionError(('relocation',t))
                relocs.append((P+r['r_offset'],v))
        syms={n:symbol(str(len(n))+n) for n in NAMES}
        dotted={'ACTIVE','BASE','START','EXPERIMENT','ARMED_SESSION'}
        syms.update({n:symbol(str(len(n))+n+('.0' if n in dotted else '')) for n in ['ACTIVE','BASE','START','CALLS','EVENTS','DROPPED','EXPERIMENT','ARMED_SESSION']})
    ks=Ks(KS_ARCH_ARM64,KS_MODE_LITTLE_ENDIAN)
    def asm(s,a):return bytes(ks.asm(s,addr=a)[0])
    # Mirrors skyline source/skyline/utils/armutils.s. x16/x17 are trampoline
    # scratch and NZCV is not saved; the selected game sites have these dead.
    backup=['sub sp, sp, #0x300']
    backup += [f'stp x{i}, x{i+1}, [sp, #{i*8}]' for i in range(0,30,2)]
    backup += ['add x0, sp, #0x300','stp x30, x0, [sp, #0xf0]']
    backup += [f'stp q{i}, q{i+1}, [sp, #{0x100+i*16}]' for i in range(0,32,2)]
    restore=[f'ldp x{i}, x{i+1}, [sp, #{i*8}]' for i in range(0,30,2)]
    restore+=['ldr x30, [sp, #0xf0]']
    restore+=[f'ldp q{i}, q{i+1}, [sp, #{0x100+i*16}]' for i in range(0,32,2)]
    restore+=['add sp, sp, #0x300','ldr x16, [x17, #0x10]','br x16']
    handler=';'.join(backup+['mov x0, sp','ldr x16, [x17, #8]','blr x16']+restore)
    def case(kind,mode,team,initialized,active=True,invalid=False,repeats=1,command=0xb4,length=0xd0,null=False,experiment=False,prepared=1,armed=False,proposal_slot=3,origin=0x1690884):
        u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        for a,n in [(P,0x110000),(R,0x1000),(S,0x30000),(ST,0x10000),(H,0x10000),(G+0x5305000,0x1000),(G+0x530a000,0x1000),(G+0x5314000,0x1000)]:u.mem_map(a,n)
        for a,b in segs:
            if b:u.mem_write(P+a,b)
        for a,v in relocs:u.mem_write(a,struct.pack('<Q',v))
        u.mem_write(syms['ACTIVE'],bytes([active]));u.mem_write(syms['BASE'],struct.pack('<Q',G))
        u.mem_write(syms['EXPERIMENT'],bytes([experiment]));u.mem_write(syms['ARMED_SESSION'],struct.pack('<Q',S if armed else 0))
        u.mem_write(syms['START'],struct.pack('<Q',0))
        u.mem_write(G+0x53050f0,struct.pack('<I',mode));u.mem_write(G+0x53144d8,bytes([initialized]))
        u.mem_write(G+0x530a981,bytes([team]));u.mem_write(S+0x269c0,struct.pack('<I',2))
        u.mem_write(S+0x26a62,bytes([prepared]))
        identity=0x77770000
        u.mem_write(S+0x9ff8,struct.pack('<Q',identity))
        for slot in range(16):u.mem_write(S+0xa010+8+slot*0x78,struct.pack('<Q',identity if slot==3 else 0x88880000+slot))
        source=S+0xa798+3*0x1350+(1 if invalid else 0)
        for a in [S+0x21fa9,S+0x24649,source+0xf11]:u.mem_write(a,bytes([team]))
        u.mem_write(R+0x11,bytes([team]));u.mem_write(R+0xc8,bytes([proposal_slot]));u.mem_write(S+0xb6a9+3*0x1350,bytes([team]))
        u.mem_write(H,asm('b '+hex(H+0x100),H))
        u.mem_write(H+0x100,struct.pack('<I',0x10000091)+asm('ldr x16, [x17]; br x16',H+0x104))
        u.mem_write(H+0x110,struct.pack('<QQQ',H+0x400,syms[NAMES[kind]],H+0x180))
        u.mem_write(H+0x400,asm(handler,H+0x400))
        u.mem_write(H+0x180,asm(MOVS[kind]+'; b '+hex(END),H+0x180))
        extrev={a:n for n,a in externals.items()}
        calls=[];reads=[]
        def code(uc,a,size,data):
            if a in extrev:
                assert extrev[a]=='_ZN2nn2os13GetSystemTickEv',extrev[a]
                calls.append(a);uc.reg_write(UC_ARM64_REG_X0,TICK);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))
        permitted_game_writes=set()
        if experiment and prepared==0 and mode==0x07010102 and initialized and team==0:
            if kind==5 and proposal_slot==3 and origin in (0x1687fec,0x1690884,0x16f52d8,0x16fa0e8):permitted_game_writes.add(R+0x11)
            if kind==0 and armed:permitted_game_writes.add(S+0x21fa9)
        def write(uc,access,a,size,value,data):
            assert P+0x20000<=a and a+size<=P+0x110000 or ST<=a and a+size<=ST+0x10000 or (size==1 and a in permitted_game_writes),('forbidden write',hex(a),size)
        def read(uc,access,a,size,value,data):
            if S<=a<S+0x30000 or R<=a<R+0x1000 or G<=a<G+0x6000000:reads.append((a,size))
        u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write);u.hook_add(UC_HOOK_MEM_READ,read)
        for repeat in range(repeats):
            vals=[0x44440000+i*0x111 for i in range(31)];vals[24]=S;vals[1]=source
            if kind==5: vals[0]=S;vals[1]=command;vals[2]=0 if null else R;vals[3]=length;vals[4]=0;vals[30]=G+origin
            if kind==6: vals[19]=S+0xa010;vals[8]=R;vals[9]=3
            if kind==7: vals[19]=S+0xa010;vals[9]=S+0xa010+3*0x1350+(1 if invalid else 0)
            for r,v in zip(X,vals):u.reg_write(r,v)
            for i in range(32):u.reg_write(UC_ARM64_REG_Q0+i,0x123456789abcdef0123456789abcdef0+i)
            u.reg_write(UC_ARM64_REG_SP,ST+0xf000);u.reg_write(UC_ARM64_REG_FPCR,0);u.reg_write(UC_ARM64_REG_FPSR,0x800009f)
            u.emu_start(H,END,count=20000)
            assert u.reg_read(UC_ARM64_REG_PC)==END
            if kind<5:vals[8]=[0x3738,0x3738,1,0x4638,0x46ac][kind]
            elif kind==5:vals[23]=vals[4]&0xffffffff
            elif kind==6:vals[10]=0x1350
            elif kind==7:vals[11]=0x16b8
            for i,(r,v) in enumerate(zip(X,vals)):
                if i not in [16,17]:assert u.reg_read(r)==v,(NAMES[kind],i,hex(u.reg_read(r)),hex(v))
            assert u.reg_read(UC_ARM64_REG_SP)==ST+0xf000
            for i in range(32):assert u.reg_read(UC_ARM64_REG_Q0+i)==0x123456789abcdef0123456789abcdef0+i
            assert u.reg_read(UC_ARM64_REG_FPCR)==0 and u.reg_read(UC_ARM64_REG_FPSR)==0x800009f
        qualifies = active and (kind!=5 or command & 0xffff == 0xb4 and length & 0xffffffff == 0xd0 and not null)
        captured=min(repeats,64) if qualifies else 0
        assert len(calls)==captured
        bank=kind+(8 if mode==0x07010102 else 0)
        # Verified release CaptureStore layout: 256 128-byte slots, then next.
        events=syms['EVENTS']+bank*0x8008
        assert struct.unpack('<Q',u.mem_read(events+0x8000,8))[0]==captured
        for i in range(captured):
            b=bytes(u.mem_read(events+i*128,128))
            participant=(proposal_slot if kind==5 and proposal_slot<16 else 3) if kind in (1,5,6,7) and not invalid else 0xff
            owner=3 if kind in (0,1) and not (invalid and kind==1) else 0xff
            changed = bool(permitted_game_writes)
            observed_team = 1 if changed and kind in (0,5) else team
            expected=bytes([kind,prepared,0xff if invalid and kind in (1,7) else observed_team,team if initialized else 0xff,initialized,participant,3,owner])
            assert b[8:16]==expected,(b[8:16],expected)
            assert struct.unpack_from('<IIQ',b,16)==(mode,2,TICK)
            origins={0x1687fec:0,0x1690884:1,0x16f52d8:2,0x16fa0e8:3}
            assert b[32]==(origins.get(origin,0xff) if kind==5 else 0xff)
            assert b[33]==((0 if kind==5 else 1) if changed else 0xff)
            assert b[120]==1 and struct.unpack_from('<Q',b)[0]==i
        assert struct.unpack('<Q',u.mem_read(syms['DROPPED'],8))[0]==(max(0,repeats-64) if qualifies else 0)
        if kind==5:
            assert bytes(u.mem_read(R+0x11,1))==bytes([1 if permitted_game_writes else team])
            assert struct.unpack('<Q',u.mem_read(syms['ARMED_SESSION'],8))[0]==(S if permitted_game_writes else (S if armed else 0))
        if kind==0:assert bytes(u.mem_read(S+0x21fa9,1))==bytes([1 if permitted_game_writes else team])
        allowed={(G+0x53050f0,4)}
        if qualifies:
            allowed|={(S+0x269c0,4),(S+0x26a62,1),(G+0x53144d8,1)}
            allowed.add((S+0x9ff8,8))
            allowed|={(S+0xa010+8+slot*0x78,8) for slot in range(16)}
            if initialized:allowed.add((G+0x530a981,1))
            if kind==0:allowed.add((S+0x21fa9,1))
            elif kind==1 and not invalid:allowed.add((source+0xf11,1))
            elif kind in (2,3,4):allowed.add((S+0x24649,1))
            elif kind==5:allowed|={(R+0x11,1),(R+0xc8,1)}
            elif kind==6:allowed.add((R+0x11,1))
            elif kind==7 and not invalid:allowed.add((S+0xb6a9+3*0x1350,1))
        assert set(reads)<=allowed,(set(reads)-allowed)
        if not qualifies:assert not reads
    cases=0
    for kind in range(8):
        for mode in [0,0x07010102]:
            for team in [0,1,0xa5]:
                for initialized in [0,1]:case(kind,mode,team,initialized);cases+=1
        case(kind,0x07010102,1,1,active=False);cases+=1
        case(kind,0x07010102,1,1,repeats=65);cases+=1
    case(1,0x07010102,1,1,invalid=True);cases+=1
    case(7,0x07010102,1,1,invalid=True);cases+=1
    for kw in [dict(command=0xb5),dict(length=0xcf),dict(length=0xd1),dict(null=True)]:
        case(5,0x07010102,1,1,**kw);cases+=1
    case(5,0x07010102,0,1,experiment=True,prepared=0);cases+=1
    case(0,0x07010102,0,1,experiment=True,prepared=0,armed=True);cases+=1
    for kw in [dict(proposal_slot=4),dict(origin=0),dict(prepared=1)]:
        case(5,0x07010102,0,1,experiment=True,**kw);cases+=1
    case(5,0,0,1,experiment=True,prepared=0);cases+=1
    case(5,0x07010102,1,1,experiment=True,prepared=0);cases+=1
    case(5,0x07010102,0,0,experiment=True,prepared=0);cases+=1
    case(0,0x07010102,0,1,experiment=True,prepared=0,armed=False);cases+=1
    return {'cases':cases,'result':'PASS','release_elf_sha256':hashlib.sha256(Path(elf_path).read_bytes()).hexdigest(),
      'scope':'Compiled callbacks under a Skyline-style register save/restore handler; exact two permitted one-byte mutation targets, guarded rejection cases, preserved registers, allowed reads, event values, inactive path, independent banks and capacity. Tick service stubbed. Not actual Switch loader or live matchmaking.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args();print(json.dumps(run(a.elf),indent=2))
