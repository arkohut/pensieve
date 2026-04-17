import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { generateLogo } from '../src/lib/logo-generator';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function generatePNGLogo(size: number, outputFileName: string) {
  const svgContent =
    size <= 256 ? generateLogo(size, false, false) : generateLogo(size, true, true);

  const logosDir = path.join(__dirname, '..', 'public', 'logos');
  if (!fs.existsSync(logosDir)) {
    fs.mkdirSync(logosDir, { recursive: true });
  }

  const outputPath = path.join(logosDir, outputFileName);
  await sharp(Buffer.from(svgContent)).png().toFile(outputPath);
}

const iconSizes = [16, 32, 64, 128, 256, 512, 1024];

(async () => {
  for (const size of iconSizes) {
    await generatePNGLogo(size, `memos_logo_${size}.png`);
    await generatePNGLogo(size * 2, `memos_logo_${size}@2x.png`);
  }
  console.log('PNG logos generated successfully in the public/logos directory!');

  const sourceFile = path.join(__dirname, '..', 'public', 'logos', 'memos_logo_128.png');
  const destinationFile = path.join(__dirname, '..', 'public', 'favicon.png');
  fs.copyFileSync(sourceFile, destinationFile);
  console.log('Favicon copied successfully to public/favicon.png');
})();
