# 内置 PDF 渲染引擎（PDFium WebAssembly）

`scripts/pdf2png.mjs` 用这套文件把 PDF 逐页渲染成 PNG，不需要 poppler、LibreOffice
或任何原生二进制；任意平台只要 Node.js 即可运行。

## 文件来源

| 文件 | 来源 | 许可 |
|---|---|---|
| `index.esm.js` | [@hyzyla/pdfium](https://github.com/hyzyla/pdfium) v2.1.13，仅取 ESM 构建 | MIT，见 `LICENSE-MIT.txt` |
| `pdfium.wasm` | 同包的 WebAssembly 构建（上游 [pdfium-lib](https://github.com/paulocoutinhox/pdfium-lib)） | BSD-3-Clause，见 `LICENSE-PDFIUM.txt` |

PDFium 是 Chromium 使用的 PDF 引擎，渲染结果与 Chrome 预览一致。

## 为什么是 v2 而不是 v3

v3 的 `package.json` 声明 `engines.node >= 22`；v2.1.13 没有这个限制，Node 18/20/22/24
都能跑，且体积更小（wasm 3.9 MB vs 5.1 MB）。两者对 `page.render()` 的调用方式一致，
`colorSpace: "BGRA"` 在 v2 和 v3 都返回 RGBA 字节序，因此升级时只需替换两个文件。

## 升级步骤

```bash
npm pack @hyzyla/pdfium@2.1.13 --pack-destination /tmp
tar -xzf /tmp/hyzyla-pdfium-2.1.13.tgz -C /tmp
cp /tmp/package/dist/index.esm.js /tmp/package/dist/pdfium.wasm /tmp/package/LICENSE.md \
   vendor/pdfium/           # LICENSE.md 另存为 LICENSE-MIT.txt
node scripts/pdf2png.mjs --input some.pdf --prefix /tmp/check   # 回归验证
```

## 不用内置引擎

`scripts/pdf2png.mjs --engine poppler` 可以改用系统的 `pdftoppm`；删掉本目录后
`--engine auto` 也会自动退回 poppler（存在时）。
