# Porting and validation checklist

## 1. Establish identity

Use [the Ghidra workflow](../ghidra/README.md) on your own 13.0.5 dump, optionally
with your own 13.0.4 reference. Keep executable hashes and versions associated
with every report. The exported version is a user-supplied label, not a version
detector; cross-check it against your dump process/game installation.

Rank candidates by structural features or the old function's instruction
sequence. Do not approve the highest score automatically. Confirm:

- Function semantics, including state sources, writes, guard checks, and any
  DLC iteration. Scalar matches alone are weak evidence.
- Actual ABI: a single x0 output pointer, no required hidden/extra arguments,
  void return contract, and the documented output lifetime.
- At least 105 bytes of output capacity where needed, and initialization of
  every byte you will observe before the original returns.
- A separate caller, relevant referenced global, and later a rule consumer.
- No concurrent use during plugin installation; no hot-loading.

Inspect a separate direct BL caller with the candidate inspector. Its first
instruction must call the entry and both 16–64-byte signatures must be unique.
If no suitable direct caller is found, stop and review the design; do not
fabricate a signature or weaken the validation.

## 2. Configure only a proven offline observer

The shipped configuration is inert. Record review notes and set the ABI/length
attestations only after disassembly review. Choose individual offsets confirmed
to hold initialized rule data. The allowlist envelope is not itself evidence.
Profile, padding, DLC, and unknown state are deliberately excluded.

Cold-launch offline with only essential loaders and this plugin. Keep a backup
of the mod setup. Verify startup, ordinary menu behavior, log creation, and
clean original-function behavior before comparing rules.

## 3. Three independent Off/On/Off cycles

For every cycle, use otherwise identical offline Team Battle states and the
same CSS transition. Capture Off, On, and return-to-Off states with explicit
labels. Do this three times using nine distinct observations. Record manually:

- menu/scene and transition;
- all non-Team-Attack rules held fixed;
- selected offsets and why each is safe to read;
- capture file and sequence for each state.

Run the comparison and A/B tools. Reject bits that fail to return, vary between
repetitions, or disappear when unrelated state is held fixed. Correlation is
not enough: trace the suspected bit into a consumer that actually tests
friendly-fire behavior and establish mask and polarity.

## 4. Prove the rules pipeline separately

An offline positive result does not prove online propagation. In an authorized,
consensual private environment, follow code references through all of:

1. preferred-rule object construction;
2. encoding for matchmaking or peer negotiation;
3. validation/defaulting and winning ruleset selection;
4. per-peer decoding;
5. battle-rule initialization and Team Attack consumer.

Record where the bit first appears, is preserved, or is overwritten. Arena,
Quickplay, co-op, and general team-battle code paths must not be treated as
interchangeable. A caller seen in the UI does not prove packet inclusion.

The present build does not log raw packets, identify peers, install network
hooks, or make any write. Add future observation only after a separate privacy
and ABI review. Do not experiment with malformed public Quickplay traffic.

## 5. Mutation is a later, conditional milestone

Only after all the above evidence exists may a separate private/opt-in build
be considered. It would require a proven private-context gate, verified field,
correct pre-negotiation point, unchanged unrelated bits, and synchronized
acceptance by all peers. There must be no public unconsented mutation,
client-only gameplay divergence, or ban-evasion mechanism.

If the game strips the field or Quickplay never serializes it, record that
negative result. Do not replace standard rule negotiation with local damage
changes and call the objective achieved.

## 6. Compatibility and release acceptance

Test alone first, then one other identified/versioned plugin at a time.
Map shared hooks and the order they are installed. Read the separate
compatibility report; no existing matrix entry is a certification.

A future functional claim requires hardware evidence: versions, plugin set,
repeated matches, per-peer state agreement, and no desync in the defined test
conditions. None of those tests was performed for this observer checkpoint.
