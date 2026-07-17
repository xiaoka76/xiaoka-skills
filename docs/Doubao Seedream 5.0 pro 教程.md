Doubao Seedream 5.0 pro（以下简称 Seedream 5.0 pro）面向高精度图片生成场景，提供更精准的位置与元素控制能力。支持文生图、单张图生图、多参考图生图（最多 10 张），以及通过交互编辑实现精准坐标定位和任意标记编辑。本文重点介绍 Seedream 5.0 pro 的专属能力，帮助您快速实现 [Image generation API](https://www.volcengine.com/docs/82379/1541523) 调用。

<span id="pro_featured"></span>
# 特色能力

Seedream 5.0 pro 新增以下特色功能：


<span aceTableMode="list" aceTableWidth="5,4"></span>
|交互编辑 |原生多语种生成 |
|---|---|
|<video src="https://arkdoc.tos-cn-beijing.volces.com/videos/image-generation/edite-model.mov" controls></video><br><br><br>> 支持通过坐标、框选、箭头等多种方式指定编辑位置，精准编辑图片，实现局部元素替换、物品定位、区域生成等精细化操作。 |<span>![图片](https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro-part2-tab3-group1-input1.png) </span><br><br>> 新增支持俄语、阿拉伯语、菲律宾语、泰语、土耳其语、韩语、马来语、西班牙语、葡萄牙语、印尼语、法语、德语、越南语、日语等 14 种语言的原生文字生成能力。 |


<span id="pro_overview"></span>
# 能力概述

以下为 Seedream 系列各版本模型的能力与参数对比，帮助您根据业务需求选择合适的模型。


<span aceTableMode="list" aceTableWidth="1.5,2,3,3,3,3"></span>
|模型名称 ||[Seedream 5.0 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-5-0-pro) |[Seedream 5.0 lite](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-5-0) |[Seedream 4.5](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-4-5) |[Seedream 4.0](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-4-0) |
|---|---|---|---|---|---|
|模型 ID (Model ID) ||doubao\-seedream\-5\-0\-pro\-260628 |doubao\-seedream\-5\-0\-260128 (同时支持：doubao\-seedream\-5\-0\-lite\-260128) |doubao\-seedream\-4\-5\-251128 |doubao\-seedream\-4\-0\-250828 |
|[文生图](https://www.volcengine.com/docs/82379/1824121#9695d195) ||✓ |✓ |✓ |✓ |
|[文生组图](https://www.volcengine.com/docs/82379/1824121#ec79cfda) ||暂不支持 |✓ |✓ |✓ |
|[单 / 多图生图](https://www.volcengine.com/docs/82379/1824121#8bc49063) ||✓ |✓ |✓ |✓ |
|[单 / 多图生组图](https://www.volcengine.com/docs/82379/1824121#fc9f85e4) ||暂不支持 |✓ |✓ |✓ |
|[交互编辑](https://www.volcengine.com/docs/82379/2582774#interactive_edit) ||✓ |✗ |✗ |✗ |
|[流式输出](https://www.volcengine.com/docs/82379/1824121#e5bef0d7) ||暂不支持 |✓ |✓ |✓ |
|[联网搜索](https://www.volcengine.com/docs/82379/1824121#4e1745fa) ||暂不支持 |✓ |✗ |✗ |
|模型参数 |分辨率 |1K, 2K |2K, 3K, 4K |2K, 4K |1K, 2K, 4K |
||输出格式 |png, jpeg |png, jpeg |jpeg |jpeg |
||提示词优化模式 |标准模式, 极速模式 |标准模式 |标准模式 |标准模式, 极速模式 |
||生成数量 |支持生成单图/多张图层 |输入的参考图数量 + 最终生成的图片数量 ≤ 15张 | | |
|限流 IPM（张 / 分钟） ||500 |500 |500 |500 |


<span id="pro_basic_usage"></span>
# 基础使用

Seedream 5.0 pro 的基础使用方式（文生图、图文生图、多图融合）与其他 Seedream 模型一致，只需将 `model` 参数替换为 `doubao-seedream-5-0-pro-260628`。详细代码示例和说明请参考：


* [文生图](https://www.volcengine.com/docs/82379/1824121#9695d195)

* [图文生图](https://www.volcengine.com/docs/82379/1824121#8bc49063)

* [多图融合](https://www.volcengine.com/docs/82379/1824121#4a35e28f)


<span id="interactive_edit"></span>
# 交互编辑

Seedream 5.0 pro 支持通过 **框选、点位、箭头、标注框、坐标** 等方式指定编辑位置，实现对局部区域的精准生成或修改。详细操作说明请参考 [Seedream 5.0 pro 交互编辑指南](https://www.volcengine.com/docs/82379/2582775)。

<span id=".5L2_55So56S65L6LLeS7u-aEj-agh-iusA=="></span>
## 使用示例\-任意标记

在参考图上通过手绘草图、涂鸦、圈选等任意标记指定编辑区域，模型将识别标记范围并在其中生成或替换内容，同时自然融入原有场景。


<span aceTableMode="list" aceTableWidth="1,1,1"></span>
|提示词 |输入图 |输出 |
|---|---|---|
|根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。 |<span>![图片](https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png) </span> |<span>![图片](https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_output2.png) </span> |



<Tabs>
<Tab zoneid="pzvdaL6KC9" title="Curl">
<TabTitle>Curl</TabTitle>

```Bash
curl https://ark.cn-beijing.volces.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "doubao-seedream-5-0-pro-260628",
    "prompt": "根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。",
    "image": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png",
    "size": "2K",
    "output_format":"png",
    "watermark": false
}'
```



* 您可按需替换 Model ID。Model ID 查询见 [模型列表](https://www.volcengine.com/docs/82379/1330310)。


</Tab>
<Tab zoneid="o3OkYCIjm2" title="Python">
<TabTitle>Python</TabTitle>

```Python
import os
# Install SDK:  pip install 'volcengine-python-sdk[ark]'
from volcenginesdkarkruntime import Ark 

client = Ark(
    # The base URL for model invocation
    base_url="https://ark.cn-beijing.volces.com/api/v3", 
    # Get API Key: https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
    api_key=os.getenv('ARK_API_KEY'), 
)
 
imagesResponse = client.images.generate( 
    # Replace with Model ID
    model="doubao-seedream-5-0-pro-260628", 
    prompt="根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。",
    image="https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png",
    size="2K",
    output_format="png",
    response_format="url",
    watermark=False
) 
 
print(imagesResponse.data[0].url)
```



</Tab>
<Tab zoneid="m3GzAIZ7xZ" title="Java">
<TabTitle>Java</TabTitle>

```Java
package com.ark.sample;


import com.volcengine.ark.runtime.model.images.generation.*;
import com.volcengine.ark.runtime.service.ArkService;
import okhttp3.ConnectionPool;
import okhttp3.Dispatcher;

import java.util.Arrays; 
import java.util.List; 
import java.util.concurrent.TimeUnit;

public class ImageGenerationsExample { 
    public static void main(String[] args) {
        String apiKey = System.getenv("ARK_API_KEY");
        ConnectionPool connectionPool = new ConnectionPool(5, 1, TimeUnit.SECONDS);
        Dispatcher dispatcher = new Dispatcher();
        ArkService service = ArkService.builder()
                .baseUrl("https://ark.cn-beijing.volces.com/api/v3") // The base URL for model invocation
                .dispatcher(dispatcher)
                .connectionPool(connectionPool)
                .apiKey(apiKey)
                .build();

        GenerateImagesRequest generateRequest = GenerateImagesRequest.builder()
                .model("doubao-seedream-5-0-pro-260628") // Replace with Model ID
                .prompt("根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。")
                .image("https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png")
                .size("2K")
                .outputFormat("png")
                .responseFormat(ResponseFormat.Url)
                .watermark(false)
                .build();
                
        ImagesResponse imagesResponse = service.generateImages(generateRequest);
        System.out.println(imagesResponse.getData().get(0).getUrl());

        service.shutdownExecutor();
    }
}
```



</Tab>
<Tab zoneid="zivXzrAwML" title="Go">
<TabTitle>Go</TabTitle>

```Go
package main

import (
    "context"
    "fmt"
    "os"
    
    "github.com/volcengine/volcengine-go-sdk/service/arkruntime"
    "github.com/volcengine/volcengine-go-sdk/service/arkruntime/model"
    "github.com/volcengine/volcengine-go-sdk/volcengine"
)

func main() {
    client := arkruntime.NewClientWithApiKey(
        os.Getenv("ARK_API_KEY"),
        // The base URL for model invocation
        arkruntime.WithBaseUrl("https://ark.cn-beijing.volces.com/api/v3"),
    )    
    ctx := context.Background()
    outputFormat := model.OutputFormatPNG

    generateReq := model.GenerateImagesRequest{
       Model:          "doubao-seedream-5-0-pro-260628",
       prompt:         "根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。",
       Image:          volcengine.String("https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png"),
       Size:           volcengine.String("2K"),
       OutputFormat:   &outputFormat,
       ResponseFormat: volcengine.String("url"),
       Watermark:      volcengine.Bool(false),
    }

    imagesResponse, err := client.GenerateImages(ctx, generateReq)
    if err != nil {
       fmt.Printf("generate images error: %v\n", err)
       return
    }

    fmt.Printf("%s\n", *imagesResponse.Data[0].Url)
}
```



</Tab>
<Tab zoneid="R6VgvBUAgY" title="OpenAI">
<TabTitle>OpenAI</TabTitle>

```Python
import os
from openai import OpenAI

client = OpenAI( 
    # The base URL for model invocation
    base_url="https://ark.cn-beijing.volces.com/api/v3", 
    # Get API Key: https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
    api_key=os.getenv('ARK_API_KEY'), 
) 

imagesResponse = client.images.generate( 
    model="doubao-seedream-5-0-pro-260628",
    prompt="根据手绘草图对图像进行编辑。在左下角标记区域添加一叠真实的杂志或艺术画册，并在右侧标记区域添加一个带杯碟的陶瓷杯咖啡。移除所有草图线条。保持构图不变。让新添加的物体自然融入原有场景中。",
    size="2K",
    output_format="png",
    response_format="url",
    extra_body = {
        "image": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_input2.png",
        "watermark": False
    }
) 

print(imagesResponse.data[0].url)
```



</Tab>
</Tabs>


<span id=".5L2_55So56S65L6LLeWdkOagh-WumuS9jQ=="></span>
## 使用示例\-坐标定位

通过在 prompt 中加入 `<point>` 或 `<bbox>` 坐标标签，精确指定跨图的编辑区域，实现主体元素的定位放置。完整调用步骤和参数说明请参考 [Seedream 5.0 pro 交互编辑指南](https://www.volcengine.com/docs/82379/2582775)。


<span aceTableMode="list" aceTableWidth="1,1.5,1"></span>
|提示词 |输入图 |输出 |
|---|---|---|
|将图 1 `<bbox> 179 283 796 986</bbox>`的主体放到图 2 `<bbox> 118 331 933 871</bbox>` 位置。 |<span>![图片](https://arkdoc.tos-cn-beijing.volces.com/images/image-generation/image-20260711-161109-398.png) </span> |<span>![图片](https://arkdoc.tos-cn-beijing.volces.com/images/image-generation/edit-image.png) </span> |


<span id=".5L2_55So6K-05piO"></span>
## 使用说明

交互编辑需要准备以下输入要素： **待编辑图片** 和 **prompt** （包含定位信息 + 编辑指令）。根据定位方式不同，分为以下两种形式：


<span aceTableMode="list" aceTableWidth="1,1"></span>
|形式 1：任意标记 + 自然语言定位 |形式 2：坐标精准定位 |
|---|---|
|在待编辑图片上通过手绘草图、涂鸦、圈选等方式标记编辑区域，然后在 prompt 中用自然语言描述标记位置和编辑意图。<br><br>```JSON```<br>```{```<br>```    "prompt": "在蓝色框内添加一个电视机"```<br>``````<br>```}```<br> |使用工具框定待编辑内容的坐标（坐标获取方式详见 [Seedream 5.0 pro 交互编辑指南](https://www.volcengine.com/docs/82379/2582775)），在 prompt 中通过 `<point>` 或 `<bbox>` 坐标标签精确指定位置。<br><br>```JSON```<br>```{```<br>```    "prompt": "将图1<bbox>179 283 796 986</bbox>的主体放到图2<bbox>118 331 933 871</bbox>位置"```<br>``````<br>```}```<br> |


准备好输入要素后，将 **待编辑图片** 和 **prompt** 一起传入 API 接口即可生成图片编辑结果。

<span id="pro_prompt_optimize"></span>
# 提示词优化模式

Seedream 5.0 pro 支持通过 `optimize_prompt_options.mode` 参数控制提示词优化的模式：


* `standard`（默认值）：标准模式，生成内容的质量更高，耗时较长。

* `fast`：快速模式，生成内容的耗时更短，效果略低于标准模式。


<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">建议</div>


<div data-tips="true" data-tips-type="tip">如您的业务对生成时延较为敏感，推荐使用 <code>fast</code> 模式以节省等待时间。</div>


```JSON
{
    "optimize_prompt_options": {
        "mode": "fast"
    }
}
```


<span id="pro_output_spec"></span>
# 自定义图片输出规格

您可以配置以下参数来控制图片输出规格：


* **size** ：指定输出图像的尺寸大小。

* **response_format** ：指定生成图像的返回格式。

* **output_format** ：指定生成图像的文件格式。

* **watermark** ：指定是否为输出图片添加水印。


<span id=".5Zu-5YOP6L6T5Ye65bC65a-4"></span>
### 图像输出尺寸

支持以下尺寸设置方式，不可混用。

**方式 1：指定分辨率档位（推荐）** 

在 prompt 中用自然语言描述图片宽高比、图片形状或图片用途，最终由模型判断生成图片的大小。


* 默认值：`2K`

* 可选值：`1K`、`2K`


使用方式 1 并在 prompt 中描述特定宽高比时，模型实际映射的宽高像素参考值如下表所示（模型支持生成的宽高比不限于以下列举的标准值，此处仅以常见宽高比为例）。


|分辨率 |宽高比 |宽高像素值 |
|---|---|---|
|1K |1:1 |1024x1024 |
||4:3 |1152x864 |
||3:4 |864x1152 |
||16:9 |1424x800 |
||9:16 |800x1424 |
||3:2 |1248x832 |
||2:3 |832x1248 |
||21:9 |1568x672 |
|2K |1:1 |2048x2048 |
||4:3 |2368x1776 |
||3:4 |1776x2368 |
||16:9 |2816x1584 |
||9:16 |1584x2816 |
||3:2 |2496x1664 |
||2:3 |1664x2496 |
||21:9 |3136x1344 |


**方式 2：指定宽高像素值（** **`宽x高`** **）** 


* 总像素取值范围：[`1280x720`（921600）, `2048x2048x1.1025`（4624220）]

* 宽高比取值范围：[1/16, 16]


<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">说明</div>


<div data-tips="true" data-tips-type="tip">采用方式 2 时，需同时满足总像素取值范围和宽高比取值范围。其中，总像素是对单张图宽度和高度的像素乘积限制，而不是对宽度或高度的单独值进行限制。</div>



* <div data-tips="true" data-tips-type="tip"><strong>有效示例</strong> ：<code>2048x1024</code></div>


   <div data-tips="true" data-tips-type="tip">总像素值 2048x1024=2097152，符合 [921600, 4624220] 的区间要求；宽高比 2048/1024=2，符合 [1/16, 16] 的区间要求，故该示例值有效。   </div>
   

* <div data-tips="true" data-tips-type="tip"><strong>无效示例</strong> ：<code>512x512</code></div>


   <div data-tips="true" data-tips-type="tip">总像素值 512x512=262144，未达到 921600 的最低要求，故该示例值无效。   </div>
   



<span aceTableMode="list" aceTableWidth="1,1"></span>
|方式1 |方式2 |
|---|---|
|```JSON```<br>```{```<br>```    "prompt": "生成一组共4张连贯插画，宽高比为3:2，核心为同一庭院一角的四季变迁，以统一风格展现四季独特色彩、元素与氛围",```<br>``````<br>```    "size": "2K"```<br>``````<br>```}```<br> |```JSON```<br>```{```<br>```    "prompt": "生成一组共4张连贯插画，核心为同一庭院一角的四季变迁，以统一风格展现四季独特色彩、元素与氛围",```<br>``````<br>```    "size": "2048x2048"```<br>``````<br>```}```<br> |


<span id=".5Zu-5YOP6L6T5Ye65pa55byP"></span>
### 图像输出方式

通过设置 **response_format** 参数，可以指定生成图像的返回方式：


* `url`：返回图片下载链接。

* `b64_json`：以 Base64 编码字符串的 JSON 格式返回图像数据。


```JSON
{
    "response_format": "url"
}
```


<span id=".5Zu-5YOP5paH5Lu25qC85byP"></span>
### 图像文件格式

通过设置 **output_format** 参数，指定生成图像文件的格式：


* `png`

* `jpeg`


```JSON
{
    "output_format": "png"
}
```


<span id=".5Zu-5YOP5Lit5re75Yqg5rC05Y2w"></span>
### 图像中添加水印

通过设置 **watermark** 参数，来控制是否在生成的图片中添加水印。


* `false`：不添加水印。

* `true`：在图片右下角添加"AI生成"字样的水印标识。


```JSON
{
    "watermark": true
}
```


<span id="pro_limits"></span>
# 使用限制

**SDK 版本升级**

为保证模型功能的正常使用，请务必升级至最新 SDK 版本。相关步骤可参考 [安装及升级 SDK](https://www.volcengine.com/docs/82379/1541595)。

**图片传入限制**


* 图片格式：jpeg、png、webp、bmp、tiff、gif、heic、heif

* 图片传入方式：

   * 图片 URL：请确保图片 URL 可被访问。

      示例：`https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_5_imageToimage.png`

   * Base64 编码：请遵循格式`data:image/<图片格式>;base64,<Base64编码>`。注意：`<图片格式>` 必须采用小写字母，例如 `data:image/png;base64,<base64_image>`。

      如需获得图片的 Base64 编码，可使用第三方工具，例如 https://base64.guru/converter/encode/image。

* 宽高比（宽/高）范围：[1/16, 16]

* 宽高长度（px） \> 14

* 大小：不超过 30 MB

* 总像素：不超过 `6000x6000=36000000` px （对单张图宽度和高度的像素乘积限制，而不是对宽度或高度的单独值进行限制）

* 最多支持传入 10 张参考图


**保存时间**

图片URL仅保留24小时，超时后会被自动清除。请您务必及时保存生成的图片。

**限流说明**


* RPM 限流：账号下同模型（区分模型版本）每分钟生成图片数量上限。若超过该限制，生成图片时会报错。

* 不同模型的限制值不同，详见 [图片生成能力](https://www.volcengine.com/docs/82379/1330310#d3e5e0eb)。




