//! Half-open peak for the independent oracle.
//!
//! No crates. The Python sweep is the reference. Ends sort before starts at
//! the same minute, so a shared endpoint occupies one lane.

#[no_mangle]
pub extern "C" fn rf_peak_exceeds(
    starts: *const i64,
    ends: *const i64,
    count: usize,
    cap: i64,
) -> i32 {
    if cap < 0 {
        return 1;
    }
    if count == 0 || starts.is_null() || ends.is_null() {
        return 0;
    }
    let starts = unsafe { std::slice::from_raw_parts(starts, count) };
    let ends = unsafe { std::slice::from_raw_parts(ends, count) };
    let mut events: Vec<(i64, i32)> = Vec::with_capacity(count.saturating_mul(2));
    for index in 0..count {
        if starts[index] >= ends[index] {
            continue;
        }
        events.push((ends[index], 0));
        events.push((starts[index], 1));
    }
    events.sort_unstable();
    let mut active: i64 = 0;
    for (_minute, kind) in events {
        if kind == 0 {
            active -= 1;
        } else {
            active += 1;
            if active > cap {
                return 1;
            }
        }
    }
    0
}
