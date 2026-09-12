# B4 rule-message path and passive observer 0.2.5

Current status, 2026-09-10: capture 0013 now supplies runtime evidence for all three new message sites. See research/capture-0013-findings.md in the source archive. The hardware-pending status and install recipe below describe the original 2026-09-08 build, not a current request to repeat the test.

Reviewed 2026-09-08 from the supplied SSBU 13.0.5 executable. Main SHA-256:
`eb79e639e47d9a0c79bcfe2ec50fc807afa9601800226627b58bd6a1a83dc52d`.
Offsets below are relative to main, loaded at 0x7100000000 during analysis.

## New static evidence

The B4 payload has the compact settings starting at +0, its Team Attack byte
at +0x11, and a session record index at +0xC8. Observed caller construction in
0x1686850 copies participant settings into a 0xD0-byte stack record and calls
0x1685CB0 with command 0xB4. Additional immediate-B4 references include callers
near 0x1690724, 0x16F52D0 and 0x16FA034; those surrounding functions have not all
been classified. Submission entering 0x1685CB0 is not proof of queue success,
transport delivery, remote ownership or acceptance.

Incoming-command dispatch at 0x1698160 uses `(command & 0xFFFF)-0xA3` and the
relative table at 0x44F3694. For B4 it reaches 0x16981C4, then the sole scanned
direct branch to 0x16F03B0 at 0x16981F0. It passes `session+0xA010` as x0.
This is a scan of immediate branch instructions, not proof of no indirect calls.

The inner dispatcher uses `(command & 0xFFFF)-0xB3` and the relative table at
0x44F3B44. B4's entry at 0x44F3B48 targets 0x16F0550. That branch obtains the
payload from descriptor+8, reads the slot at payload+0xC8, and rejects slots
above 15. Its length check rejects values above 0xD0, not every undersized
value; the original function relies on earlier buffer/descriptor validity.
The observer adds no access beyond the original path's existing payload reads.

The selected destination is `manager + slot*0x1350 + 0x1688`, equivalently
`session + slot*0x1350 + 0xB698`. A word copied at 0x16F0594 carries payload
byte +0x11 unchanged to `session+slot*0x1350+0xB6A9`. The branch later marks
`session+slot*0x1350+0xBAC0` bit 0. This is the same participant settings layout
used by the captured 0.2.4 selection/application path. It does not prove that
Quickplay sends or accepts an ON proposal across all participants.

## New passive hook sites

| Site | Sample | Live registers and permitted extra reads |
|---|---|---|
| 0x1685CCC | rule_submit | Original entry arguments x0=session, w1=command, x2=buffer, w3=length; only B4/D0, read buffer+11 and C8 |
| 0x16F056C | rule_receive_before | x19=manager, x8=payload, x9=validated slot; read payload+11 |
| 0x16F0598 | rule_receive_team_stored | x19=manager, x9=manager+slot*1350; read destination+1699 after original Team Attack store |

The two receive samples derive session by subtracting 0xA010 from the manager,
as established by the direct caller. They also sample the existing session
request/prepared and guarded global rule fields, without retaining pointers.
The previous five application sites are retained. Logging is restricted to
rule byte, bounded record slot, mode, request, preparation flag and ticks.

The original instructions are MOV w23,w4, MOV w10,#0x1350 and MOV w11,#0x16B8.
Each callback uses an immutable InlineCtx. x16/x17 and NZCV are dead at these
sites: submit is in the entry prologue before any original call; the receive
sites follow the final index conditional and have no subsequent conditional
use of its flags. No replacement original call is made. Exact code segments
and the B4 receive table entry are validated before installing single-branch
inline patches and checking both neighboring words.

## Checks and next operator action

51 original native dispatch/copy cases passed on private synthetic buffers,
covering all 16 slots and OFF/ON/A5 plus oversize and invalid-index rejection;
no helper stubs were used. 118 tests of actual compiled observer callbacks
passed with a Skyline-style save/restore handler and a deterministic tick stub.
Host tests (31), Python tests (15), and host/Switch Clippy passed. The 0.2.5
hooks have not run on the user's Switch yet.

Install ssbu-rule-message-observer-0.2.5.zip and follow NEXT_TEST.md: startup in
airplane mode, then one normal co-op doubles match with both players active,
20 seconds at results, close game, power off, upload the newest log and report
completion/errors. Keep offline Team Attack OFF and other settings constant.
Do not repeat the completed offline damage or earlier baseline test. No new
main dump, Ghidra export or menu assets are needed.

The outcome can be a B4 path observed, or zero new-path events. Both are useful;
a zero count is not proof of no reception, and no automatic repeat is requested.
A receive event may be local dispatch/loopback; it does not identify the remote
sender or prove agreement. This is not a rule override or a ban-safety result.
