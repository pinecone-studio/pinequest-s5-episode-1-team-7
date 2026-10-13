/** Joins class names, skipping falsy values: cn('a', cond && 'b'). */
export const cn = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(' ')
