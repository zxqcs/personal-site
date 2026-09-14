import sharp from "sharp"

const input = {
  create: {
    width: 16,
    height: 16,
    channels: 4,
    background: { r: 40, g: 90, b: 140, alpha: 1 },
  },
}

const encoded = await sharp(input).png().toBuffer()
const metadata = await sharp(encoded).metadata()

if (metadata.format !== "png" || metadata.width !== 16 || metadata.height !== 16) {
  throw new Error(`Unexpected sharp output: ${JSON.stringify(metadata)}`)
}

console.log("sharp image pipeline verified")
