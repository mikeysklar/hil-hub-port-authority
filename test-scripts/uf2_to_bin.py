"""T13: convert a UF2 to a raw flash image for openocd `program <bin> <base>`.

usage: python3 uf2_to_bin.py firmware.uf2 [out.bin]    default out: fw.bin
Prints the family ID, base address, end address and size. Program at the
printed base, for example (RP2350, raspberrypi openocd fork):
  openocd ... -f target/rp2350.cfg -c "program fw.bin 0x10000000 verify reset exit"
Gaps between blocks are filled with 0xFF. Blocks flagged not-main-flash are
skipped. Refuses a file that mixes family IDs, since openocd would get both.
"""
import struct, sys

UF2_MAGIC = (0x0A324655, 0x9E5D5157)
NOT_MAIN_FLASH = 0x00000001
FAMILY_PRESENT = 0x00002000

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "fw.bin"
data = open(src, "rb").read()
if len(data) % 512:
    sys.exit(f"{src}: size {len(data)} is not a multiple of 512, not a UF2")

blocks = {}
fams = set()
for i in range(0, len(data), 512):
    b = data[i:i + 512]
    m0, m1, flags, addr, size, blk, nblk, fam = struct.unpack("<8I", b[:32])
    if (m0, m1) != UF2_MAGIC:
        sys.exit(f"{src}: bad magic in block at offset {i}")
    if flags & NOT_MAIN_FLASH:
        continue
    if flags & FAMILY_PRESENT:
        fams.add(fam)
    blocks[addr] = b[32:32 + size]

if len(fams) > 1:
    sys.exit(f"{src}: mixed families {[hex(f) for f in fams]}, refusing")
lo = min(blocks)
hi = max(a + len(d) for a, d in blocks.items())
img = bytearray(b"\xff" * (hi - lo))
for a, d in blocks.items():
    img[a - lo:a - lo + len(d)] = d
open(out, "wb").write(img)
print(f"{out}: family {[hex(f) for f in fams]} base {hex(lo)} end {hex(hi)} "
      f"bytes {len(img)} blocks {len(blocks)}")
