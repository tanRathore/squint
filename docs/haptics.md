# the haptic grammar

squint has no screen, so the vibration motor is the whole interface. The grammar below is
shared by the Android and iPhone clients and emitted by the server as a waveform
(`haptic.pattern` in ms, `haptic.amplitudes` 0–255), so a verdict feels identical on both.

## principles

1. **One press, one answer.** Every press ends in exactly one verdict pattern. No chains, no
   "wait for more".
2. **Length means certainty.** The longer the buzz, the stronger the claim. The strongest claim
   we make (likely AI) is the only single long pulse; everything weaker is shorter or broken up.
3. **Count means category.** One = synthetic, two = no AI signals, three = can't tell. People
   remember counts better than rhythms.
4. **Never silent.** A press that produced nothing is a bug. Failure has its own pattern.
5. **Say less than you know.** The whisper is one sentence; the evidence lives in the app for
   anyone who wants it later.

## vocabulary

| moment                     | pattern (ms on)             | feel                       |
|----------------------------|-----------------------------|----------------------------|
| press acknowledged         | 25 @ 35%                    | a tick, immediately        |
| still working (>1.6 s)     | 18, pause, 18 @ 25%         | a faint double tap         |
| index already knows        | tick again when the quick answer comes back with sightings ≥ 2 |
| **likely synthetic**       | **650 @ 100%**              | one long, unmistakable     |
| leaning synthetic          | 420 @ 100%, 110 @ 65%       | long then short            |
| can't tell                 | 70 ×3 @ 80%                 | three quick taps           |
| no AI signals / leaning human | 110 ×2 @ 65%             | two short                  |
| camera-verified capture    | 90 @ 55%, 380 @ 100%        | short then long, rising    |
| correction noted           | 40 ×2 @ 45%                 | two tiny taps              |
| failed (no network, blocked screen) | 40 ×4 @ 45%        | four tiny taps             |

Amplitude carries confidence inside a tier where the hardware allows it (Android amplitude
control, Core Haptics intensity). On motors without amplitude control the counts and lengths
alone still disambiguate every row.

## the second press

Pressing again on the same screen within 45 seconds means "that was wrong". The server compares
the perceptual hash of the new screenshot with the previous verdict's hash; on a match it files
feedback instead of re-checking and answers with the two-tiny-taps pattern and "Noted, thanks."
No screen, no button, no typing. It is the only way most people will ever correct the index, so it
had to be free.

## earcons

Phones on tables don't get felt. With the tone option on, each pattern is also played as a
synthesised tone through the accessibility audio stream: long pulses at 392 Hz, short ones at
784 Hz, same durations. Generated on the fly, no assets, ducked under whatever is playing.

## the whisper

One sentence, at 55–60 % volume, on the accessibility/assistance stream so it goes to earbuds
when they're in and stays quiet otherwise. Never the word "real". It always names the strongest
piece of evidence and, when the index has seen the thing before, how many times and since when.
Available in English, Spanish, Portuguese and Hindi from the phone's locale.

## what we deliberately don't do

- No pattern for "probably fine, but…". Hedges don't survive translation into vibration.
- No continuous buzzing while working. Attention is the cost; a faint double tap at 1.6 s is the
  ceiling.
- No different pattern per detector. Users don't care which model said it.
