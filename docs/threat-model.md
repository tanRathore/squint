# threat model

## adversaries

**The generator author.** Wants their output to pass. Can strip metadata (trivial), add noise,
recompress, crop, screenshot. Our answer: metadata is a bonus, not the basis. Detectors rotate.
The index is the thing they can't route around, because the index doesn't care how a file was
made, only whether this exact thing has been seen before, when, and what people said about it.

**The spreader.** Re-encodes and re-crops a known fake to defeat lookups. pHash survives resize,
recompress and mild crops (hamming ≤10). Heavy crops fall to detectors. Video frames are sampled
so trimming the start doesn't matter; audio landmarks vote on relative offsets so trimming doesn't
matter there either.

**The poisoner.** Mass-reports real photos as AI, or AI as human, to corrupt the index. Feedback
enters the fusion only as a `history` signal whose reliability caps at 0.7 and needs ≥3 labels to
move at all; it never overrides provenance. One device carries at most one label per
fingerprint: sending feedback again, for the same check or for a fresh check of the same image,
replaces the earlier label instead of adding a vote, so a loop of POSTs buys nothing. Sightings count devices, not requests: a device that checks the same fingerprint
fifty times in a day moves `sightings`, `p_mean`, trending and the webhook thresholds exactly
once (`Index_.seen_from`). Rate limits are per device and per IP on top of that.

**The double-presser.** The second press files "wrong" with no friction, so it is the cheapest
poisoning vector. It files `unsure`, which is read against the verdict it answers: a "wrong"
on *likely synthetic* counts as one human vote, on *leaning human* as one AI vote, on *unclear*
as nothing. It is still one vote per check per device, subject to the ≥3 rule above, and it can
never reach past `history`'s cap. Labelled corrections still require a button (telegram) or the
list in the app.

**The pivot.** Registers a webhook pointing at `169.254.169.254`, `localhost:5432` or a sibling
container and lets the server do the knocking. Webhook hosts are resolved and refused if any
address is loopback, private, link-local or reserved, both when registered and again right
before each delivery; the delivery then connects to the exact address that passed (Host and SNI
carry the real hostname), so a rebinding answer between the check and the connect goes nowhere,
and deliveries never follow redirects.

**The bomber.** Uploads a 20 KB PNG that decodes to 12,000 × 9,000. Images over 80 megapixels
are refused before decoding unless they are JPEGs, which are decoded at reduced scale; PIL's
own decompression-bomb guard stays on as the backstop.

**The scraper.** Wants our index. `/v1/lookup` returns aggregate facts about a hash you already
have; it can't enumerate. Partner endpoints need keys.

**The curious operator.** That's us. See `privacy.md`: there is nothing to look at.

## failure modes we accept and label

- *Unclear* is a real answer and the default when evidence is thin. The haptic for it is distinct.
- Screenshots of screenshots degrade everything; we say "share the original file" in that case.
- Apps with `FLAG_SECURE` (banking) give the assistant no screenshot. We say so.
- Text detection is the weakest modality. Stylometry carries 0.15 reliability and says so. For
  emails the useful output is often the phishing pattern note, not the AI verdict.
- A camera-signed C2PA manifest can be attached to anything by someone with a signing key. We say
  "camera verified by content credentials", not "real".

## abuse of the product itself

Someone could use squint to check their own fakes before posting. They could do that with any
public detector already; we add nothing to that capability and we do keep the fingerprint,
which means the eventual post is already in the index when the first stranger presses the button.
