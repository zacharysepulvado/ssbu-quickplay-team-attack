//! Reviewed 13.0.5 leaf codec ABI and private-buffer validation.
//! These routines touch only their two argument objects. They are not match setup.
pub const ENCODER_OFFSET: usize = 0x16a4920;
pub const DECODER_OFFSET: usize = 0x16a4b60;
pub const TABLE_OFFSET: usize = 0x50831c0;
pub const SCALARS: [usize; 13] = [1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 14, 19, 20];
pub const FLAGS: [usize; 7] = [9, 13, 15, 17, 21, 22, 23];

#[repr(C)]
pub struct Descriptor {
    pub table: usize,
    pub rule: *mut u8,
}

#[repr(C)]
pub struct Cursor {
    pub buffer: *mut u8,
    pub capacity: u32,
    pub position: u32,
}

// Both reviewed instruction bodies leave x0 equal to the input descriptor.
// Preserve that register value even though the observed callers ignore it.
pub type CodecFn = unsafe extern "C" fn(*mut Descriptor, *mut Cursor) -> usize;

/// Exercise verified leaf code on plugin-owned buffers only.
/// # Safety
/// Both functions must implement exactly the reviewed ABI and bounded leaf body.
pub unsafe fn self_test(encoder: CodecFn, decoder: CodecFn) -> Result<usize, String> {
    let mut calls = 0;
    for flags in 0..128u8 {
        let mut source = [0xA5u8; 56];
        for off in SCALARS {
            source[16 + off] = (off as u8).wrapping_mul(17).wrapping_add(flags & !2);
        }
        for (bit, off) in FLAGS.iter().enumerate() {
            source[16 + off] = (flags >> bit) & 1;
        }
        let source_before = source;
        let mut stream = [0xCC; 64];
        let pos = if flags & 1 == 0 { 7 } else { 31 };
        let mut desc = Descriptor {
            table: 0,
            rule: source.as_mut_ptr().wrapping_add(16),
        };
        let mut cursor = Cursor {
            buffer: stream.as_mut_ptr(),
            capacity: 64,
            position: pos,
        };
        let returned = unsafe { encoder(&mut desc, &mut cursor) };
        calls += 1;
        let mut expected_stream = [0xCC; 64];
        for (i, off) in SCALARS.iter().enumerate() {
            expected_stream[pos as usize + i] = source_before[16 + off];
        }
        expected_stream[pos as usize + 13] = flags;
        if returned != &mut desc as *mut Descriptor as usize
            || desc.table != 0
            || desc.rule != source.as_mut_ptr().wrapping_add(16)
            || cursor.buffer != stream.as_mut_ptr()
            || cursor.capacity != 64
            || cursor.position != pos + 14
            || source != source_before
            || stream != expected_stream
        {
            return Err(format!(
                "encoder private-buffer check failed at flags {flags:02X}"
            ));
        }
        let mut output = [0xA5; 56];
        desc.rule = output.as_mut_ptr().wrapping_add(16);
        cursor.position = pos;
        let returned = unsafe { decoder(&mut desc, &mut cursor) };
        calls += 1;
        let mut expected_output = [0xA5; 56];
        for off in SCALARS.into_iter().chain(FLAGS) {
            expected_output[16 + off] = source_before[16 + off];
        }
        if returned != &mut desc as *mut Descriptor as usize
            || desc.table != 0
            || desc.rule != output.as_mut_ptr().wrapping_add(16)
            || cursor.buffer != stream.as_mut_ptr()
            || cursor.capacity != 64
            || cursor.position != pos + 14
            || output != expected_output
            || stream != expected_stream
        {
            return Err(format!(
                "decoder private-buffer roundtrip failed at flags {flags:02X}"
            ));
        }
    }
    for flags in 0..=255u8 {
        let mut stream = [0x63; 64];
        stream[20] = flags;
        let before = stream;
        let mut output = [0xA5; 56];
        let mut desc = Descriptor {
            table: 0,
            rule: output.as_mut_ptr().wrapping_add(16),
        };
        let mut cursor = Cursor {
            buffer: stream.as_mut_ptr(),
            capacity: 64,
            position: 7,
        };
        let returned = unsafe { decoder(&mut desc, &mut cursor) };
        calls += 1;
        let mut expected = [0xA5; 56];
        for off in SCALARS {
            expected[16 + off] = 0x63;
        }
        for (bit, off) in FLAGS.iter().enumerate() {
            expected[16 + off] = (flags >> bit) & 1;
        }
        if returned != &mut desc as *mut Descriptor as usize
            || cursor.position != 21
            || desc.table != 0
            || desc.rule != output.as_mut_ptr().wrapping_add(16)
            || cursor.buffer != stream.as_mut_ptr()
            || cursor.capacity != 64
            || output != expected
            || stream != before
        {
            return Err(format!(
                "decoder private-buffer bit check failed at flags {flags:02X}"
            ));
        }
    }
    Ok(calls)
}

#[cfg(test)]
mod tests {
    use super::*;
    unsafe extern "C" fn encode(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
        unsafe {
            let rule = (*desc).rule;
            let out = (*cursor).buffer.add((*cursor).position as usize);
            for (i, off) in SCALARS.iter().enumerate() {
                *out.add(i) = *rule.add(*off);
            }
            let mut flags = *rule.add(9);
            for (bit, off) in FLAGS.iter().enumerate().skip(1) {
                flags |= u8::from(*rule.add(*off) != 0) << bit;
            }
            *out.add(13) = flags;
            (*cursor).position += 14;
        }
        desc as usize
    }
    unsafe extern "C" fn decode(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
        unsafe {
            let rule = (*desc).rule;
            let input = (*cursor).buffer.add((*cursor).position as usize);
            for (i, off) in SCALARS.iter().enumerate() {
                *rule.add(*off) = *input.add(i);
            }
            for (bit, off) in FLAGS.iter().enumerate() {
                *rule.add(*off) = (*input.add(13) >> bit) & 1;
            }
            (*cursor).position += 14;
        }
        desc as usize
    }
    unsafe extern "C" fn bad_neighbor(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
        let result = unsafe { encode(desc, cursor) };
        unsafe {
            *(*cursor).buffer.add((*cursor).position as usize - 1) ^= 4;
        }
        result
    }
    unsafe extern "C" fn bad_guard(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
        let result = unsafe { decode(desc, cursor) };
        unsafe {
            *(*desc).rule.add(24) = 0;
        }
        result
    }
    #[test]
    fn private_suite_accepts_codec_and_rejects_neighbor_or_guard_corruption() {
        assert_eq!(unsafe { self_test(encode, decode) }.unwrap(), 512);
        assert!(unsafe { self_test(bad_neighbor, decode) }.is_err());
        assert!(unsafe { self_test(encode, bad_guard) }.is_err());
    }
    #[test]
    fn reviewed_argument_layout() {
        assert_eq!(std::mem::size_of::<Descriptor>(), 16);
        assert_eq!(std::mem::offset_of!(Descriptor, rule), 8);
        assert_eq!(std::mem::size_of::<Cursor>(), 16);
        assert_eq!(std::mem::offset_of!(Cursor, position), 12);
    }
}
