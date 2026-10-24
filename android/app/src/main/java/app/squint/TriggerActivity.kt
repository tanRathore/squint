package app.squint

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity

class TriggerActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        finish()
        Handler(Looper.getMainLooper()).postDelayed({
            SquintInteractionService.live?.trigger("quick_tile")
                ?: (application as SquintApp).whisper.say("Set squint as your assistant first.")
        }, 450)
    }
}
