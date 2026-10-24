package app.squint.device

import app.squint.Verdict

class VerdictCache(private val maxAgeMs: Long = 6 * 60 * 60 * 1000L, private val maxSize: Int = 200) {
    private val map = object : LinkedHashMap<String, Pair<Long, Verdict>>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Pair<Long, Verdict>>?) = size > maxSize
    }

    @Synchronized
    fun put(phash: String, v: Verdict) {
        map[phash] = System.currentTimeMillis() to v
    }

    @Synchronized
    fun near(phash: String, maxDistance: Int = 6): Verdict? {
        val now = System.currentTimeMillis()
        var best: Pair<Int, Verdict>? = null
        for ((k, entry) in map) {
            if (now - entry.first > maxAgeMs) continue
            val d = PHash.distance(k, phash)
            if (d <= maxDistance && (best == null || d < best.first)) best = d to entry.second
        }
        return best?.second
    }
}
