package app.squint

import android.content.Context
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSession.AssistState
import android.view.View
import kotlinx.coroutines.launch

class SquintSession(ctx: Context) : VoiceInteractionSession(ctx) {
    private val app get() = context.applicationContext as SquintApp
    private val main = Handler(Looper.getMainLooper())
    private var shot: Bitmap? = null
    private var info: ScreenInfo? = null
    private var trigger = "assistant"
    private var fired = false
    private var gotScreenshotFlag = false

    override fun onCreateContentView(): View {
        return View(context).apply { visibility = View.GONE }
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        shot = null
        info = null
        fired = false
        trigger = args?.getString("trigger") ?: "assistant"
        gotScreenshotFlag = (showFlags and SHOW_WITH_SCREENSHOT) != 0
        app.haptics.ack()
        main.postDelayed({ fire() }, 900)
    }

    override fun onHandleAssist(state: AssistState) {
        super.onHandleAssist(state)
        if (state.index == 0 || info == null) {
            info = AssistHint.read(state.assistStructure)
        }
        maybeFire()
    }

    override fun onHandleScreenshot(screenshot: Bitmap?) {
        super.onHandleScreenshot(screenshot)
        shot = screenshot
        maybeFire()
    }

    private fun maybeFire() {
        if (shot != null && info != null) fire()
    }

    private fun fire() {
        if (fired) return
        fired = true
        main.removeCallbacksAndMessages(null)
        val bmp = shot
        val meta = info ?: ScreenInfo("", null, "")
        hide()
        if (bmp == null) {
            if (!gotScreenshotFlag && !app.prefs.warnedAboutScreenshot) {
                app.prefs.warnedAboutScreenshot = true
                app.whisper.say(context.getString(R.string.say_need_screenshot))
            } else if (meta.text.split(Regex("\\s+")).size > 40) {
                runText(meta)
                return
            } else {
                app.haptics.failed()
                if (app.prefs.speak) app.whisper.say(context.getString(R.string.say_secure_screen))
            }
            return
        }
        var answered = false
        val thinking = Runnable { if (!answered) app.haptics.thinking() }
        main.postDelayed(thinking, 1600)
        app.scope.launch {
            val out = app.checker.screenFlow(bmp, meta, trigger) { early ->
                if (early.verdict.seenBefore >= 2) app.haptics.ack()
            }
            answered = true
            main.removeCallbacks(thinking)
            deliver(out)
        }
    }

    private fun runText(meta: ScreenInfo) {
        app.scope.launch {
            deliver(app.checker.checkText(meta.text, meta.packageName))
        }
    }

    private fun deliver(out: Outcome?) {
        if (out == null) {
            app.haptics.failed()
            if (app.prefs.speak) app.whisper.say(context.getString(R.string.say_unreachable))
            return
        }
        app.deliver(out.verdict, out.offline)
    }

    override fun onHide() {
        super.onHide()
        shot = null
    }
}
