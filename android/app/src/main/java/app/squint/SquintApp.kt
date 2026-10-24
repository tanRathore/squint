package app.squint

import android.app.Application
import android.util.Log
import app.squint.device.ScreenModel
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class SquintApp : Application() {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO + CoroutineExceptionHandler { _, e -> Log.w("squint", "background job died: ${e.message}") })
    lateinit var prefs: Prefs
    lateinit var haptics: Haptics
    lateinit var whisper: Whisper
    lateinit var earcons: Earcons
    lateinit var checker: Checker
    lateinit var scorer: LocalScorer
    lateinit var screen: ScreenModel

    override fun onCreate() {
        super.onCreate()
        instance = this
        prefs = Prefs(this)
        haptics = Haptics(this)
        whisper = Whisper(this)
        earcons = Earcons()
        scorer = LocalScorer(this)
        screen = ScreenModel(this)
        checker = Checker(this, prefs, scorer, screen)
    }

    fun deliver(v: Verdict, offline: Boolean = false) {
        haptics.play(v.pattern, v.amplitudes)
        if (prefs.earcons) earcons.play(v.pattern, v.amplitudes)
        if (prefs.speak) whisper.say(v.say)
    }

    companion object {
        lateinit var instance: SquintApp
            private set
    }
}
