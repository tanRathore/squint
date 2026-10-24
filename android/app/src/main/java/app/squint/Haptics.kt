package app.squint

import android.content.Context
import android.os.Build
import android.os.VibrationAttributes
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

class Haptics(ctx: Context) {
    private val vibrator: Vibrator = if (Build.VERSION.SDK_INT >= 31) {
        (ctx.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        ctx.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
    }

    fun play(pattern: LongArray, amplitudes: IntArray) {
        if (!vibrator.hasVibrator() || pattern.isEmpty()) return
        val amps = if (vibrator.hasAmplitudeControl()) amplitudes else IntArray(pattern.size) { if (amplitudes.getOrElse(it) { 0 } > 0) VibrationEffect.DEFAULT_AMPLITUDE else 0 }
        val effect = VibrationEffect.createWaveform(pattern, amps, -1)
        if (Build.VERSION.SDK_INT >= 33) {
            vibrator.vibrate(effect, VibrationAttributes.createForUsage(VibrationAttributes.USAGE_ACCESSIBILITY))
        } else {
            vibrator.vibrate(effect)
        }
    }

    fun ack() = play(longArrayOf(0, 25), intArrayOf(0, 90))

    fun thinking() = play(longArrayOf(0, 18, 120, 18), intArrayOf(0, 60, 0, 60))

    fun failed() = play(longArrayOf(0, 40, 70, 40, 70, 40, 70, 40), intArrayOf(0, 120, 0, 120, 0, 120, 0, 120))

    fun demo(tier: String) {
        val (p, a) = when (tier) {
            "likely_synthetic" -> longArrayOf(0, 650) to intArrayOf(0, 255)
            "leaning_synthetic" -> longArrayOf(0, 420, 110, 110) to intArrayOf(0, 255, 0, 170)
            "unclear" -> longArrayOf(0, 70, 70, 70, 70, 70) to intArrayOf(0, 200, 0, 200, 0, 200)
            "verified_capture" -> longArrayOf(0, 90, 80, 380) to intArrayOf(0, 140, 0, 255)
            else -> longArrayOf(0, 110, 110, 110) to intArrayOf(0, 160, 0, 160)
        }
        play(p, a)
    }
}
