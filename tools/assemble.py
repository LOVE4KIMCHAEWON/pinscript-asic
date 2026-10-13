#!/usr/bin/env python3
"""PinScript assembler, pure Python stdlib. Labels resolve to 6-bit addresses.

Usage: python3 tools/assemble.py firmware/uart_tx.asm --out build/uart_tx
Output: .hex (16-bit word lines), .bin (one SPI WRITE command), .lst.
Send .bin during one active-low CS frame. Release CS, then separately send
bytes 0x02, 0x00 to run at PC=0 (one new CS frame).
"""
import argparse
from pathlib import Path
import re

OP = {
    'NOP':0x0000, 'HALT':0x0001, 'LDI':0x1000, 'LDX':0x2000,
    'SHOWA':0x5300, 'SHOWB':0x5700,
    'OUT':0x3000, 'DIR':0x4000, 'OUTA':0x5000, 'IN':0x6000,
    'SHR':0x7000, 'SHL':0x7001, 'LOOP':0x8000, 'JMP':0x9000,
    'JZ':0xA000, 'JNZ':0xB000, 'WAIT':0xC000, 'DBIT':0xD000,
    'TEST':0xE000, 'XORO':0xF000, 'XORD':0xF080,
    'SHINL':0x5100, 'SHINR':0x5200,
    'SHINLB':0x5500, 'SHINRB':0x5600,
}
BARE = {'NOP','HALT','OUTA','IN','SHR','SHL','SHOWA','SHOWB'}
BRANCH = {'LOOP','JMP','JZ','JNZ'}
IMM8 = {'LDI','LDX','OUT','DIR','WAIT','TEST'}


def parse(source: str):
    lines, labels = [], {}
    for lineno, line in enumerate(source.splitlines(), 1):
        line = re.split(r'[;#]', line, maxsplit=1)[0].strip()
        if not line:
            continue
        if ':' in line:
            name, sep, rest = line.partition(':')
            name = name.strip()
            if not re.fullmatch(r'[a-zA-Z_]\w*', name):
                raise ValueError(f'line {lineno}: malformed label {name}')
            if name in labels:
                raise ValueError(f'line {lineno}: duplicate label {name}')
            labels[name] = len(lines)
            line = rest.strip()
        if line:
            opcode, *tail = line.split(maxsplit=1)
            args = [x.strip() for x in tail[0].split(',')] if tail else []
            lines.append((lineno, opcode.upper(), args, line))
    if len(lines) > 64:
        raise ValueError(f'program has {len(lines)} instructions (maximum 64)')
    return lines, labels


def assemble(source: str):
    lines, labels = parse(source)
    words = []
    for lineno, name, args, original in lines:
        try:
            if name not in OP:
                raise ValueError(f'unknown opcode {name}')
            instruction = OP[name]
            if name in BARE:
                if args: raise ValueError('takes no operands')
            elif name in ('SHINL', 'SHINR', 'SHINLB', 'SHINRB'):
                if len(args) != 1: raise ValueError('expects one pin number')
                pin = int(args[0], 0)
                if not 0 <= pin <= 7: raise ValueError('pin must be 0..7')
                instruction |= pin
            elif name == 'DBIT':
                if len(args) < 3 or len(args) > 4:
                    raise ValueError('DBIT expects pin, lsb|msb, out|oe, [invert|normal]')
                pin = int(args[0], 0)
                if not 0 <= pin <= 7: raise ValueError('pin must be 0..7')
                if args[1].lower() not in ('lsb','msb'):
                    raise ValueError('select lsb|msb')
                if args[2].lower() not in ('out','oe'):
                    raise ValueError('select out|oe')
                if len(args) == 4 and args[3].lower() not in ('invert','normal'):
                    raise ValueError('select invert|normal')
                instruction |= pin
                instruction |= (args[1].lower() == 'msb') << 3
                instruction |= (args[2].lower() == 'oe') << 4
                instruction |= (len(args) == 4 and args[3].lower() == 'invert') << 5
            else:
                if len(args) != 1: raise ValueError('expects one operand')
                value = labels[args[0]] if args[0] in labels else int(args[0], 0)
                if name in BRANCH:
                    if not 0 <= value <= 63: raise ValueError('branch address 0..63')
                elif name in ('XORO','XORD'):
                    if not 0 <= value <= 127: raise ValueError('XOR mask 0..127')
                elif name in IMM8:
                    if not 0 <= value <= 255: raise ValueError('immediate 0..255')
                instruction |= value
            words.append(instruction)
        except (ValueError, KeyError) as exc:
            raise ValueError(f'line {lineno}: {original}: {exc}') from exc
    return words, lines


def pack_spi(words, addr=0):
    if not 0 <= addr <= 63 or len(words) + addr > 64:
        raise ValueError('SPI program does not fit from chosen address')
    out = bytearray([0x01, addr])
    for word in words:
        out.extend((word >> 8, word & 0xff))
    return bytes(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--out', type=Path, help='output prefix, default source stem in build/')
    args = p.parse_args()
    prefix = args.out or Path('build') / args.source.stem
    prefix.parent.mkdir(parents=True, exist_ok=True)
    words, lines = assemble(args.source.read_text(encoding='utf-8'))
    prefix.with_suffix('.hex').write_text(''.join(f'{x:04x}\n' for x in words))
    prefix.with_suffix('.bin').write_bytes(pack_spi(words))
    prefix.with_suffix('.lst').write_text(''.join(
        f'{i:02d}  {word:04X}  {item[3]}\n'
        for i, (word,item) in enumerate(zip(words,lines))))
    print(f'{args.source}: {len(words)} / 64 words -> {prefix}.[hex|bin|lst]')

if __name__ == '__main__':
    main()
