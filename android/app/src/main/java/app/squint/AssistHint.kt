package app.squint

import android.app.assist.AssistStructure
import android.graphics.Rect

data class ScreenInfo(val packageName: String, val mediaRect: Rect?, val text: String)

object AssistHint {
    private val mediaClasses = listOf("ImageView", "VideoView", "SurfaceView", "TextureView", "PlayerView", "GLSurfaceView", "ZoomableDraweeView", "SimpleDraweeView", "ReactImageView")

    fun read(structure: AssistStructure?): ScreenInfo {
        if (structure == null) return ScreenInfo("", null, "")
        val pkg = structure.activityComponent?.packageName ?: ""
        var best: Rect? = null
        var bestArea = 0L
        val text = StringBuilder()
        for (i in 0 until structure.windowNodeCount) {
            val win = structure.getWindowNodeAt(i)
            walk(win.rootViewNode, win.left, win.top, text) { r ->
                val area = r.width().toLong() * r.height().toLong()
                if (area > bestArea && r.width() > 120 && r.height() > 120) {
                    bestArea = area
                    best = r
                }
            }
        }
        return ScreenInfo(pkg, best, text.toString().trim())
    }

    private fun walk(node: AssistStructure.ViewNode, ox: Int, oy: Int, text: StringBuilder, onMedia: (Rect) -> Unit) {
        val x = ox + node.left - node.scrollX
        val y = oy + node.top - node.scrollY
        val cls = node.className ?: ""
        if (node.visibility == android.view.View.VISIBLE) {
            if (mediaClasses.any { cls.endsWith(it) }) {
                onMedia(Rect(x, y, x + node.width, y + node.height))
            }
            val t = node.text
            if (!t.isNullOrBlank() && t.length > 1 && text.length < 6000) {
                text.append(t).append('\n')
            }
        }
        for (i in 0 until node.childCount) walk(node.getChildAt(i), x, y, text, onMedia)
    }
}
