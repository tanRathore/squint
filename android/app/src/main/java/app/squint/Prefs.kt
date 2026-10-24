package app.squint

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import java.util.UUID

class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("squint", Context.MODE_PRIVATE)

    var server: String
        get() = sp.getString("server", BuildConfig.DEFAULT_SERVER)!!.trimEnd('/')
        set(v) = sp.edit().putString("server", v.trim().trimEnd('/')).apply()

    var speak: Boolean
        get() = sp.getBoolean("speak", true)
        set(v) = sp.edit().putBoolean("speak", v).apply()

    var earcons: Boolean
        get() = sp.getBoolean("earcons", false)
        set(v) = sp.edit().putBoolean("earcons", v).apply()

    var cropOnly: Boolean
        get() = sp.getBoolean("crop_only", true)
        set(v) = sp.edit().putBoolean("crop_only", v).apply()

    var sendText: Boolean
        get() = sp.getBoolean("send_text", true)
        set(v) = sp.edit().putBoolean("send_text", v).apply()

    var offlineFallback: Boolean
        get() = sp.getBoolean("offline", true)
        set(v) = sp.edit().putBoolean("offline", v).apply()

    val lang: String
        get() {
            val code = Locale.getDefault().language.lowercase()
            return if (code in setOf("en", "es", "pt", "hi")) code else "en"
        }

    var deviceId: String
        get() {
            val cur = sp.getString("device_id", null)
            if (cur != null) return cur
            val fresh = UUID.randomUUID().toString()
            sp.edit().putString("device_id", fresh).apply()
            return fresh
        }
        set(v) = sp.edit().putString("device_id", v).apply()

    fun rotateId() {
        deviceId = UUID.randomUUID().toString()
    }

    var tutorialDone: Boolean
        get() = sp.getBoolean("tutorial", false)
        set(v) = sp.edit().putBoolean("tutorial", v).apply()

    fun rememberLast(v: Verdict) {
        sp.edit().putString("last_check", v.checkId).putString("last_phash", v.phash).putLong("last_ts", System.currentTimeMillis()).apply()
    }

    fun last(): Triple<String, String, Long>? {
        val id = sp.getString("last_check", null) ?: return null
        val ph = sp.getString("last_phash", "") ?: ""
        if (ph.isEmpty() || id.startsWith("local-")) return null
        return Triple(id, ph, sp.getLong("last_ts", 0L))
    }

    fun remember(v: Verdict, app: String) {
        if (v.feedbackRecorded) return
        val arr = JSONArray(sp.getString("recent", "[]"))
        val row = JSONObject()
            .put("id", v.checkId)
            .put("tier", v.tier)
            .put("headline", v.headline)
            .put("app", app)
            .put("at", System.currentTimeMillis())
        val out = JSONArray().put(row)
        for (i in 0 until minOf(arr.length(), 9)) out.put(arr.get(i))
        sp.edit().putString("recent", out.toString()).apply()
        rememberLast(v)
    }

    fun recent(): List<JSONObject> {
        val arr = JSONArray(sp.getString("recent", "[]"))
        return (0 until arr.length()).map { arr.getJSONObject(it) }
    }

    var warnedAboutScreenshot: Boolean
        get() = sp.getBoolean("warned_shot", false)
        set(v) = sp.edit().putBoolean("warned_shot", v).apply()
}
