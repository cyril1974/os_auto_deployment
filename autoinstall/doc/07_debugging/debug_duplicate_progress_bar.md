# Bug: Duplicate Progress Bar During Package Download

## Symptom

Two progress bars are printed to the terminal during the offline package
download phase, where only one should appear:

```
[*] Downloading 187 package(s) for jammy...
Progress: |████████████████████████████████████████| 100.0% Complete

Progress: |                                        | 100.0% Complete
[*] Password hashed successfully
```

The second progress bar is either blank or visually inconsistent depending on
the terminal.

---

## Debug Steps

### 1. Locate all progress bar output statements

Searched `main.go` for `Progress` and `printProgress`:

```
Line 546: printProgress(i+1, total, pkg+" [cached]")
Line 549: printProgress(i+1, total, pkg+" [downloading]")
Line 565: fmt.Printf("\rProgress: |%s| 100.0%% Complete\n", strings.Repeat("█", 40))
Line 591: func printProgress(cur, total int, label string) { ... }
```

Found **two** places that emit a "100.0% Complete" line inside
`downloadExtraPackages()`: the last `printProgress()` call (from the loop)
and a standalone `fmt.Printf` after the loop.

### 2. Trace terminal cursor position at the point of the second print

`printProgress` uses ANSI escape sequences to do an in-place update:

```go
func printProgress(cur, total int, label string) {
    // ...
    if cur > 1 {
        fmt.Printf("\033[1A\033[2K")   // cursor UP 1 line, then clear that line
    }
    fmt.Printf("Progress: |%s| %5.1f%% Complete\n", bar, pct)
    // \n leaves cursor on the BLANK LINE below the bar
}
```

After the final `printProgress(total, total, ...)` call (last package),
the cursor lands on an **empty new line** below the 100% bar.

The post-loop code was:

```go
if total > 0 {
    fmt.Printf("\rProgress: |%s| 100.0%% Complete\n", strings.Repeat("█", 40))
}
```

The `\r` (carriage return) moves the cursor to column 0 of the **current
line** — which is already the blank line below the completed bar. It does
**not** move back up to overwrite the first bar. The result is a second
`Progress:` line printed on that blank line.

### 3. Confirm the post-loop print is always redundant

Both branches of the download loop call `printProgress`:

```go
for i, pkg := range filtered {
    if len(matches) > 0 {
        printProgress(i+1, total, pkg+" [cached]")   // cached branch
        continue
    }
    printProgress(i+1, total, pkg+" [downloading]")  // download branch
    // ...
}
```

On the last iteration (`i+1 == total`), `printProgress(total, total, ...)`
is always called regardless of whether the package was cached or downloaded.
At that point `pct == 100.0` and `filled == 40`, so the full bar is already
printed. The post-loop `fmt.Printf` is **always** redundant.

---

## Root Cause

The post-loop finalizer:

```go
if total > 0 {
    fmt.Printf("\rProgress: |%s| 100.0%% Complete\n", strings.Repeat("█", 40))
}
```

was originally intended as a guaranteed "seal" to show 100% completion.
However, because `printProgress` uses `\033[1A\033[2K` (cursor up + clear
line) and ends with `\n`, the cursor is always left on the blank line
**below** the printed bar. The `\r` in the post-loop print moves to column 0
of that blank line rather than overwriting the first bar, producing a second
visible progress bar.

---

## Resolution

Removed the redundant post-loop `fmt.Printf` in
`autoinstall/build-iso-go/main.go`.

Before:
```go
    }   // end of for i, pkg := range filtered
    if total > 0 {
        fmt.Printf("\rProgress: |%s| 100.0%% Complete\n", strings.Repeat("█", 40))
    }

    // Copy from cache to ISO extra pool
```

After:
```go
    }   // end of for i, pkg := range filtered

    // Copy from cache to ISO extra pool
```

The loop's last iteration already calls `printProgress(total, total, ...)`
which prints a complete bar. No additional print is needed.

---

## Expected Output After Fix

```
[*] Downloading 187 package(s) for jammy...
Progress: |████████████████████████████████████████| 100.0% Complete
[*] Password hashed successfully
```

Single progress bar, updated in-place throughout the download, finalised at
100% with no duplicate line.
