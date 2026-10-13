# PinScript architecture and cycle contract

## Scope

PinScript is a tiny **protocol I/O processor**, not a conventional CPU with
RAM and software stack. 64 words of writable instruction memory, a 6-bit PC,
8-bit registers `A`, `B`, and `X`, a zero flag, a stall counter, and firmware
control of 8 bidirectional GPIO form the entire datapath. A separate
input-only SPI programming transport loads the instruction RAM and invokes
RUN/HALT. Protocol software is runtime-reprogrammable.

## Storage and ports

| Element | Width | Reset on rst_n=0 | Usage |
| --- | ---: | --- | --- |
| `code_mem[0:63]` | 1024 bits | No, uninitialized | Instruction words; writable via config SPI |
| `pc` | 6 | 0 | Address of next instruction |
| `a` | 8 | 0 | Transmission accumulator, shifts and ALU flag ops |
| `b` | 8 | 0 | Independent receive shift accumulator |
| `x` | 8 | 0 | Counted loop register |
| `gpio_out` | 8 | 0 | Output latch, irrespective of output enable |
| `gpio_oe` | 8 | 0 | 1 = drive output, 0 = input/high-impedance |
| `z` | 1 | 1 | Conditional branch zero flag |
| `wait_left` | 8 | 0 | Number of stall cycles remaining |
| `running` | 1 | 0 | Enables fetching/execution when ena=1 |
| `result_byte` + `show_result` | 9 | 0 | Optional received data debug bus |

Debug output is `uo_out={running,z,pc}` unless SHOWA/SHOWB has selected the
result byte. WRITE/HALT config commands return uo_out to debug mode. RUN resets A/B/X/PC/GPIO/OE/Z/result and starts at the chosen
entrypoint. Write halts execution. HALT instruction keeps GPIO latch and OE.
Synchronous reset clears state but does not clear program memory.

## Timing

At each positive `clk` edge, if both `running` and `ena` are 1:

1. If `wait_left>0`, decrement it; no instruction issues.
2. Otherwise, read `code_mem[pc]`, default advance `pc=(pc+1)&63`, and execute
   the instruction. Branch instructions may override the next PC.
3. `WAIT N` issues once, loads `wait_left=N`, then skips execution for N
   additional rising edges: total `N+1` edge periods before the next opcode.
4. `LOOP target`: if X=0 fall through; otherwise decrement X and jump to
   target iff the decremented value is nonzero.

No pipelining or branch delay slots. Registers are updated via nonblocking
assignments, so multiple instructions never execute on one rising edge.
When `ena=0`, CPU state stalls, but SPI loader remains functional.

## ISA table

| Word pattern | Mnemonic | Result |
| --- | --- | --- |
| 0000 | NOP | do nothing |
| 0001 | HALT | stop running |
| 10nn | LDI n | A←n, Z=(n=0) |
| 20nn | LDX n | X←n |
| 30nn | OUT n | gpio_out←n |
| 40nn | DIR n | gpio_oe←n |
| 5000 | OUTA | gpio_out←A |
| 510p / 520p | SHINL p / SHINR p | sample uio_in[p] into A, update Z |
| 550p / 560p | SHINLB p / SHINRB p | sample uio_in[p] into B, update Z |
| 5300 / 5700 | SHOWA / SHOWB | publish A or B on uo_out |
| 6000 | IN | A←uio_in, Z=(A=0) |
| 7000 / 7001 | SHR / SHL | shift A one bit, zero-fill, update Z |
| 80aa | LOOP address | counted branch as above |
| 90aa | JMP address | jump |
| A0aa / B0aa | JZ / JNZ address | branch on Z |
| C0nn | WAIT n | N additional stalled cycles |
| D0bb | DBIT p, lsb/msb, out/oe, invert | copy optional-inverted A bit into pin latch/OE |
| E0nn | TEST n | Z=((A&n)==0) |
| F0nn / F0(80+nn) | XORO n / XORD n | toggle gpio_out or gpio_oe lower 7 bits |

`n` is 8-bit immediate unless XORO/XORD, where n is 0..127.
`p` is a 3-bit GPIO index. Branch addresses range 0..63.

## SPI loader

`ui[0]=SCK`, `ui[1]=MOSI`, `ui[2]=CS_N`. Other `ui` bits reserved.
SCK and CS_N use three-register sampling chains. SCK rising edges compare
stages 1 and 2; MOSI is sampled from stage 1 (two flip-flops of latency),
aligned with that edge detector. The unused third MOSI register is removed
by synthesis. CS_N selection uses stage 2. This digital oversampling scheme
requires conservative SPI setup/hold timing; simulation does not establish
physical metastability performance.
The loader samples SCK rising transitions after synchronization and shifts
one MSB-first bit at a time. Commands, with one CS-low frame per command:

- `01 AA HH LL [HH LL ...]`: WRITE from instruction address AA (wrap at 63)
- `02 EE`: RUN from EE, zero/reset CPU execution state
- `03`: HALT (preserves GPIO state)

At 12 MHz use conservative 250 kHz configuration SPI with CS setup/hold.
There is **no readback, CRC, SCK clock recovery, or status acknowledgement**.
RAM has no reset; always load a valid program before RUN.

## SPI full-duplex corrected example

A carries TX byte `0x96`; `DBIT 1, msb, out` presents MOSI. Rising SCK is
generated after 4 clock periods of setup. `SHINLB 3` shifts MISO into B,
then `SHL` advances TX A. SCK is lowered 6 system clock periods after rising
and rises again 6 periods later (1 MHz at 12 MHz). After eight clocks,
`SHOWB` emits B on the dedicated output, with MOSI verified independently.

## Electrical limitations

`uio_out` and `uio_oe` must be connected to TT-compatible bidirectional
pads. For I2C, the firmware always drives `gpio_out[1:0]=0` and pulls a line
low by setting OE; releasing OE requires external pull-ups. All sampled
`uio_in` values are expected to reflect resolved pad voltages. Physical
pad delay and pull-up rise time are not modeled by the ISA reference model.
