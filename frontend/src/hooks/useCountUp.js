import { useState, useEffect, useRef } from 'react'

export function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)
  const startTime = useRef(null)
  const startValue = useRef(0)

  useEffect(() => {
    startValue.current = value
    startTime.current = performance.now()

    let frame
    const animate = (now) => {
      const elapsed = now - startTime.current
      const t = Math.min(elapsed / duration, 1)
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3)
      const current = startValue.current + (target - startValue.current) * eased
      setValue(current)
      if (t < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
    // eslint-disable-next-line
  }, [target, duration])

  return value
}
