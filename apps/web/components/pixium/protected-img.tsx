"use client";

import { ImgHTMLAttributes, forwardRef } from "react";

/**
 * <ProtectedImg> — wraps a regular <img> with anti-download protections for
 * bundled showcase imagery (landing, explore, gallery samples, type/style
 * thumbnails). It is NOT a hard lock — DevTools can always inspect URLs — but
 * it stops the casual "right-click → Save image" path and drag-to-desktop.
 *
 * Protections applied:
 *   - contextmenu disabled (blocks right-click menu over the image)
 *   - draggable=false (blocks drag-to-desktop / drag-to-tab)
 *   - user-select: none + pointer-events through to parent for overlay
 *   - WebkitTouchCallout: "none" (blocks iOS long-press preview/save)
 *
 * Use the regular <img> tag for user-generated images (gallery, history, focused
 * result tiles in /generate) where Download IS the expected action.
 */
type Props = ImgHTMLAttributes<HTMLImageElement>;

export const ProtectedImg = forwardRef<HTMLImageElement, Props>(function ProtectedImg(
  { className, style, onContextMenu, onDragStart, ...rest },
  ref
) {
  return (
    <img
      ref={ref}
      {...rest}
      draggable={false}
      onContextMenu={(e) => {
        e.preventDefault();
        onContextMenu?.(e);
      }}
      onDragStart={(e) => {
        e.preventDefault();
        onDragStart?.(e);
      }}
      className={className}
      style={{
        userSelect: "none",
        WebkitUserSelect: "none",
        WebkitTouchCallout: "none",
        pointerEvents: "auto",
        ...style,
      }}
    />
  );
});
