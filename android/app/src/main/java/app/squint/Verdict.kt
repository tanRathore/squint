package app.squint

import org.json.JSONObject

data class Verdict(
    val checkId: String,
    val kind: String,
    val tier: String,
    val p: Double,
    val confidence: String,
    val headline: String,
    val say: String,
    val pattern: LongArray,
    val amplitudes: IntArray,
    val evidence: List<String>,
    val seenBefore: Int,
    val phash: String = "",
    val quick: Boolean = false,
    val decisive: Boolean = true,
    val feedbackRecorded: Boolean = false,
) {
    companion object {
        fun parse(json: String): Verdict {
            val o = JSONObject(json)
            val h = o.getJSONObject("haptic")
            val pat = h.getJSONArray("pattern")
            val amp = h.getJSONArray("amplitudes")
            val ev = o.optJSONArray("evidence")
            val seen = o.optJSONObject("seen_before")
            return Verdict(
                checkId = o.getString("check_id"),
                kind = o.getString("kind"),
                tier = o.getString("tier"),
                p = o.getDouble("p"),
                confidence = o.optString("confidence", "low"),
                headline = o.optString("headline", ""),
                say = o.optString("say", ""),
                pattern = LongArray(pat.length()) { pat.getLong(it) },
                amplitudes = IntArray(amp.length()) { amp.getInt(it) },
                evidence = if (ev == null) emptyList() else (0 until ev.length()).map { ev.getString(it) },
                seenBefore = seen?.optInt("sightings", 0) ?: 0,
                phash = if (o.isNull("phash")) "" else o.optString("phash", ""),
                quick = o.optBoolean("quick", false),
                decisive = o.optBoolean("decisive", true),
                feedbackRecorded = o.optBoolean("feedback_recorded", false),
            )
        }
    }
}
