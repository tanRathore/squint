package app.squint

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ShareActivity : AppCompatActivity() {
    private val app get() = application as SquintApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action != Intent.ACTION_SEND && intent?.action != Intent.ACTION_PROCESS_TEXT) {
            finish()
            return
        }
        val from = referrer?.host ?: callingPackage ?: "share"
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()
        val uri: Uri? = intent.getParcelableExtra(Intent.EXTRA_STREAM)
        app.haptics.ack()
        Toast.makeText(this, getString(R.string.looking), Toast.LENGTH_SHORT).show()
        app.scope.launch {
            val out = when {
                uri != null -> readAndCheck(uri, from)
                !text.isNullOrBlank() -> app.checker.checkText(text, from)
                else -> null
            }
            withContext(Dispatchers.Main) {
                if (out == null) {
                    app.haptics.failed()
                    Toast.makeText(this@ShareActivity, getString(R.string.could_not_check), Toast.LENGTH_SHORT).show()
                } else {
                    app.deliver(out.verdict, out.offline)
                    Toast.makeText(this@ShareActivity, out.verdict.headline, Toast.LENGTH_LONG).show()
                }
                finish()
            }
        }
    }

    private fun readAndCheck(uri: Uri, from: String): Outcome? {
        return try {
            val mime = contentResolver.getType(uri) ?: intent.type ?: "application/octet-stream"
            val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
            if (bytes.size > 25 * 1024 * 1024) return null
            app.checker.checkBytes(bytes, uri.lastPathSegment ?: "shared", mime, from)
        } catch (e: Exception) {
            Log.w("squint", "couldn't read what was shared: ${e.message}")
            null
        }
    }
}
