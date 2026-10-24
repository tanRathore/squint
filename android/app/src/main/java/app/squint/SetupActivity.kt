package app.squint

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.widget.doAfterTextChanged
import androidx.lifecycle.lifecycleScope
import app.squint.databinding.ActivitySetupBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.util.Date

class SetupActivity : AppCompatActivity() {
    private lateinit var b: ActivitySetupBinding
    private val app get() = application as SquintApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivitySetupBinding.inflate(layoutInflater)
        setContentView(b.root)

        b.server.setText(app.prefs.server)
        b.server.doAfterTextChanged { if (!it.isNullOrBlank()) app.prefs.server = it.toString() }
        bind(b.speak, app.prefs.speak) { app.prefs.speak = it }
        bind(b.earcons, app.prefs.earcons) { app.prefs.earcons = it; if (it) app.earcons.play(longArrayOf(0, 110, 110, 110), intArrayOf(0, 160, 0, 160)) }
        bind(b.cropOnly, app.prefs.cropOnly) { app.prefs.cropOnly = it }
        bind(b.sendText, app.prefs.sendText) { app.prefs.sendText = it }
        bind(b.offline, app.prefs.offlineFallback) { app.prefs.offlineFallback = it }

        b.openSettings.setOnClickListener {
            try {
                startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS))
            } catch (e: Exception) {
                startActivity(Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS))
            }
        }
        b.tryIt.setOnClickListener { tutorial() }
        b.rotate.setOnClickListener {
            app.prefs.rotateId()
            app.haptics.ack()
        }
        b.models.text = "${getString(R.string.models_label)}: detector ${if (app.scorer.available) getString(R.string.model_present) else getString(R.string.model_absent)} · screen ${if (app.screen.available) getString(R.string.model_present) else getString(R.string.model_absent)}"
    }

    private fun bind(sw: com.google.android.material.materialswitch.MaterialSwitch, value: Boolean, onChange: (Boolean) -> Unit) {
        sw.isChecked = value
        sw.setOnCheckedChangeListener { _, v -> onChange(v) }
    }

    private fun tutorial() {
        val steps = listOf(
            Triple("likely_synthetic", getString(R.string.tutorial_likely), 0L),
            Triple("unclear", getString(R.string.tutorial_unclear), 2600L),
            Triple("no_ai_signals", getString(R.string.tutorial_clean), 5200L),
        )
        for ((tier, line, delay) in steps) {
            b.root.postDelayed({
                app.whisper.say(line)
                b.root.postDelayed({ app.haptics.demo(tier); if (app.prefs.earcons) app.earcons.play(demoPattern(tier).first, demoPattern(tier).second) }, 1500)
            }, delay)
        }
        app.prefs.tutorialDone = true
        b.root.postDelayed({ refresh() }, 300)
    }

    private fun demoPattern(tier: String) = when (tier) {
        "likely_synthetic" -> longArrayOf(0, 650) to intArrayOf(0, 255)
        "unclear" -> longArrayOf(0, 70, 70, 70, 70, 70) to intArrayOf(0, 200, 0, 200, 0, 200)
        else -> longArrayOf(0, 110, 110, 110) to intArrayOf(0, 160, 0, 160)
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val isAssistant = Settings.Secure.getString(contentResolver, "assistant")?.startsWith(packageName) == true
        val shots = Settings.Secure.getInt(contentResolver, "assist_screenshot_enabled", 1) == 1
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val earbuds = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).any { it.type in setOf(android.media.AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, android.media.AudioDeviceInfo.TYPE_WIRED_HEADSET, android.media.AudioDeviceInfo.TYPE_WIRED_HEADPHONES, android.media.AudioDeviceInfo.TYPE_USB_HEADSET, android.media.AudioDeviceInfo.TYPE_BLE_HEADSET) }
        step(b.statusAssistant, isAssistant, R.string.step_assistant)
        step(b.statusScreenshot, shots, R.string.step_screenshot)
        step(b.statusTried, app.prefs.tutorialDone, R.string.step_try)
        step(b.statusEarbuds, earbuds, R.string.step_earbuds)
        renderRecent()
    }

    private fun step(tv: TextView, ok: Boolean, label: Int) {
        tv.text = "${if (ok) "✓" else "○"}   ${getString(label)}   ·   ${getString(if (ok) R.string.status_ok else R.string.status_missing)}"
        tv.alpha = if (ok) 0.6f else 1f
        tv.contentDescription = "${getString(label)}, ${getString(if (ok) R.string.status_ok else R.string.status_missing)}"
    }

    private fun showDetails(checkId: String, headline: String) {
        lifecycleScope.launch {
            val v = withContext(Dispatchers.IO) { app.checker.details(checkId) }
            val body = if (v == null) getString(R.string.details_unavailable) else (listOf(v.say) + v.evidence.map { "•  $it" }).joinToString("\n\n")
            AlertDialog.Builder(this@SetupActivity)
                .setTitle(v?.headline ?: headline)
                .setMessage(body)
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }
    }

    private fun renderRecent() {
        b.recent.removeAllViews()
        val rows = app.prefs.recent()
        if (rows.isEmpty()) {
            b.recent.addView(TextView(this).apply { text = getString(R.string.nothing_yet) })
            return
        }
        val fmt = DateFormat.getTimeInstance(DateFormat.SHORT)
        for (r in rows) {
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, 10, 0, 10) }
            val label = TextView(this).apply {
                text = "${fmt.format(Date(r.optLong("at")))}  ${r.optString("headline")}  ·  ${r.optString("app").substringAfterLast('.')}"
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                setOnClickListener { showDetails(r.optString("id"), r.optString("headline")) }
            }
            val wrong = TextView(this).apply {
                text = getString(R.string.wrong)
                setPadding(24, 0, 0, 0)
                contentDescription = getString(R.string.wrong)
                setOnClickListener {
                    app.scope.launch { app.checker.feedback(r.optString("id"), "unsure") }
                    visibility = View.INVISIBLE
                    app.haptics.ack()
                }
            }
            row.addView(label)
            row.addView(wrong)
            b.recent.addView(row)
        }
    }
}
