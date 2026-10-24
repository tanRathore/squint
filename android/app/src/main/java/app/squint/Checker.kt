package app.squint

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Rect
import android.util.Log
import app.squint.device.Offline
import app.squint.device.PHash
import app.squint.device.ScreenModel
import app.squint.device.VerdictCache
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.concurrent.TimeUnit

class Outcome(val verdict: Verdict, val fromCache: Boolean = false, val offline: Boolean = false)

class Checker(private val ctx: Context, private val prefs: Prefs, private val scorer: LocalScorer, private val screen: ScreenModel) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()
    val cache = VerdictCache()

    fun screenFlow(shot: Bitmap, info: ScreenInfo, trigger: String, onQuick: (Outcome) -> Unit): Outcome? {
        var rect = info.mediaRect?.let { clamp(it, shot.width, shot.height) }
        var kind = ""
        if (rect == null && screen.available) {
            val g = screen.guess(shot)
            if (g != null) {
                kind = g.kind
                rect = g.rect?.let { clamp(it, shot.width, shot.height) }
            }
        }
        val crop = if (prefs.cropOnly && rect != null) Bitmap.createBitmap(shot, rect.left, rect.top, rect.width(), rect.height()) else shot
        val hint = if (rect != null && crop === shot) "${rect.left},${rect.top},${rect.right},${rect.bottom}" else ""
        val phash = PHash.of(crop)
        cache.near(phash)?.let { cached ->
            if (cached.decisive) return Outcome(cached, fromCache = true)
        }
        val prev = prefs.last()
        val fields = mutableMapOf("source_app" to info.packageName, "trigger" to trigger, "hint" to hint, "lang" to prefs.lang)
        if (prev != null) {
            fields["prev_check"] = prev.first
            fields["prev_phash"] = prev.second
            fields["prev_ts"] = (prev.third / 1000.0).toString()
        }
        val small = jpeg(downscale(crop, 720), 80)
        val quick = try {
            post("v1/quick", small, "Screenshot.jpg", fields, info.packageName)
        } catch (e: IOException) {
            return offline(crop, info, phash, kind)
        }
        if (quick != null) {
            if (quick.feedbackRecorded) return Outcome(quick)
            if (quick.decisive) {
                cache.put(phash, quick)
                return Outcome(quick)
            }
            onQuick(Outcome(quick))
        }
        val localP = scorer.score(crop)
        val full = fields.toMutableMap()
        full.remove("prev_check"); full.remove("prev_phash"); full.remove("prev_ts")
        full["screen_text"] = if (prefs.sendText) info.text.take(8000) else ""
        full["local_p"] = localP?.toString() ?: ""
        val v = try {
            post("v1/check", jpeg(downscale(crop, 1600), 90), "Screenshot.jpg", full, info.packageName)
        } catch (e: IOException) {
            return offline(crop, info, phash, kind)
        } ?: return null
        if (v.decisive && v.tier != "unclear") cache.put(phash, v)
        return Outcome(v)
    }

    private fun offline(crop: Bitmap, info: ScreenInfo, phash: String, kind: String): Outcome? {
        if (!prefs.offlineFallback) return null
        val v = Offline.verdict(crop, null, scorer, prefs.lang, phash)
        return Outcome(v, offline = true)
    }

    fun checkBytes(bytes: ByteArray, name: String, mime: String, app: String): Outcome? {
        val fields = mapOf("source_app" to app, "trigger" to "share", "lang" to prefs.lang)
        return try {
            post("v1/check", bytes, name, fields, app)?.let { Outcome(it) }
        } catch (e: IOException) {
            if (!prefs.offlineFallback || !mime.startsWith("image/")) return null
            val bmp = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return null
            Outcome(Offline.verdict(bmp, bytes, scorer, prefs.lang, PHash.of(bmp)), offline = true)
        }
    }

    fun checkText(text: String, app: String): Outcome? {
        val url = endpoint("v1/check/text") ?: return null
        val json = org.json.JSONObject().put("text", text).put("source_app", app).put("lang", prefs.lang).toString()
        val req = Request.Builder()
            .url(url)
            .header("X-Device", prefs.deviceId)
            .post(json.toRequestBody("application/json".toMediaType()))
            .build()
        return try { send(req, app)?.let { Outcome(it) } } catch (e: IOException) { null }
    }

    fun details(checkId: String): Verdict? {
        if (checkId.startsWith("local-")) return null
        val url = endpoint("v1/check/$checkId") ?: return null
        val req = Request.Builder().url(url).header("X-Device", prefs.deviceId).get().build()
        return try {
            http.newCall(req).execute().use { resp ->
                val text = resp.body?.string()
                if (resp.isSuccessful && text != null) Verdict.parse(text) else null
            }
        } catch (e: Exception) {
            Log.w("squint", "couldn't fetch check $checkId: ${e.message}")
            null
        }
    }

    fun feedback(checkId: String, label: String) {
        if (checkId.startsWith("local-")) return
        val url = endpoint("v1/feedback") ?: return
        val json = org.json.JSONObject().put("check_id", checkId).put("label", label).toString()
        val req = Request.Builder().url(url).post(json.toRequestBody("application/json".toMediaType())).build()
        try { http.newCall(req).execute().close() } catch (e: Exception) { Log.w("squint", "feedback didn't go through: ${e.message}") }
    }

    private fun endpoint(path: String): HttpUrl? {
        val base = prefs.server.toHttpUrlOrNull() ?: run {
            Log.w("squint", "server url isn't valid yet: ${prefs.server}")
            return null
        }
        return base.newBuilder().addPathSegments(path).build()
    }

    private fun post(path: String, bytes: ByteArray, name: String, fields: Map<String, String>, app: String): Verdict? {
        val url = endpoint(path) ?: return null
        val b = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", name, bytes.toRequestBody("image/jpeg".toMediaType()))
        for ((k, v) in fields) b.addFormDataPart(k, v)
        val req = Request.Builder().url(url).header("X-Device", prefs.deviceId).post(b.build()).build()
        return send(req, app)
    }

    private fun send(req: Request, app: String): Verdict? {
        val resp = http.newCall(req).execute()
        try {
            val text = resp.body?.string() ?: return null
            if (!resp.isSuccessful) {
                Log.w("squint", "server said ${resp.code}: ${text.take(200)}")
                return null
            }
            val v = Verdict.parse(text)
            prefs.remember(v, app)
            return v
        } catch (e: Exception) {
            Log.w("squint", "bad reply: ${e.message}")
            return null
        } finally {
            resp.close()
        }
    }

    private fun downscale(b: Bitmap, maxSide: Int): Bitmap {
        val longest = maxOf(b.width, b.height)
        if (longest <= maxSide) return b
        val s = maxSide.toFloat() / longest
        return Bitmap.createScaledBitmap(b, (b.width * s).toInt(), (b.height * s).toInt(), true)
    }

    private fun jpeg(b: Bitmap, q: Int) = ByteArrayOutputStream().also { b.compress(Bitmap.CompressFormat.JPEG, q, it) }.toByteArray()

    private fun clamp(r: Rect, w: Int, h: Int): Rect? {
        val out = Rect(maxOf(0, r.left), maxOf(0, r.top), minOf(w, r.right), minOf(h, r.bottom))
        return if (out.width() > 64 && out.height() > 64) out else null
    }
}
