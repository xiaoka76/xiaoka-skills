Doubao Seedream 5.0 pro（以下简称 Seedream 5.0 pro）面向高精度图片生成场景，提供更精准的位置与元素控制能力。支持文生图、单张图生图、多参考图生图（最多 10 张），通过交互编辑实现精准坐标定位和任意标记编辑，以及将单张图片拆分为底图与多个图层。本文重点介绍 Seedream 5.0 pro 的专属能力，帮助您快速实现 [Image generation API](https://www.volcengine.com/docs/82379/1541523) 调用。

<span id="pro_featured"></span>
# 特色能力

Seedream 5.0 pro 新增以下特色功能：


<span aceTableMode="list" aceTableWidth="4,4,4"></span>
|交互编辑 |图层拆分 |原生多语种生成 |
|---|---|---|
|<video src="https://arkdoc.tos-cn-beijing.volces.com/videos/image-generation/edite-model.mov" controls></video><br><br><br>> 支持通过坐标、框选、箭头等多种方式指定编辑位置，精准编辑图片，实现局部元素替换、物品定位、区域生成等精细化操作。 |支持将单张图片的主体、背景、文字、装饰元素等内容自动拆解为 1 张底图和最多 16 个独立且带透明通道的图层，便于移动、缩放、替换、调色等二次编辑。 |<span>![图片](https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro-part2-tab3-group1-input1.png) </span><br><br>> 新增支持俄语、阿拉伯语、菲律宾语、泰语、土耳其语、韩语、马来语、西班牙语、葡萄牙语、印尼语、法语、德语、越南语、日语等 14 种语言的原生文字生成能力。 |


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
|模型参数 |分辨率 |1K, 1.5K, 2K |2K, 3K, 4K |2K, 4K |1K, 2K, 4K |
||输出格式 |png, jpeg |png, jpeg |jpeg |jpeg |
||提示词优化模式 |标准模式, 极速模式 |标准模式 |标准模式 |标准模式, 极速模式 |
||生成数量 |支持生成单图/多张图层（1 张底图 + 16 张图层） |输入的参考图数量 + 最终生成的图片数量 ≤ 15张 | | |
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
<span id="layer_decomposition"></span>
# 图层拆分

Seedream 5.0 pro 支持将单张输入图片中的主体、背景、文字、装饰元素等内容自动拆解为 1 张底图和最多 16 个可独立编辑的图层。每个图层均为带透明通道的 PNG 图片，模型还会返回图层的坐标、层级顺序和内容说明，便于在设计工具、前端画布中继续移动、缩放、替换、调色和重新组合。


<span id=".5ouG5YiG5Y2V5byg5Zu-54mH"></span>
## 拆分单张图片

配置参数 `layer_decomposition` 为 `true` 即可开启图层拆分模式。开启后，`image` 为必选参数，且仅支持传入 1 张待拆分图片；`prompt` 为可选参数，用于描述要拆分哪些元素。


### 提示词输入方式

使用图层拆分功能，推荐采用以下三种输入方式：


<span aceTableMode="list" aceTableWidth="1.5,4"></span>
|使用目标 |`prompt` 写法 |
|---|---|
|自动拆出主要元素 |不传入 `prompt`。模型自动识别图片中的主体、文字、背景、装饰元素等主要内容，并逐一拆分为独立图层。 |
|指定拆分对象 |在 `prompt` 中用自然语言描述待拆分的元素，例如“拆出人物、标题文字和右下角装饰图标”。可配合在输入图上标记（涂鸦、圈选等）辅助定位。 |
|精准指定区域 |在 `prompt` 中通过 `<bbox>` 坐标标签指定待拆分元素的位置。坐标采用归一化坐标（范围 0~999）。 |


```JSON
{
    "prompt": "将图片中的内容拆成 7 个图层，包括 6 组文字：<bbox>180 64 812 198</bbox>、<bbox>757 210 939 280</bbox>、<bbox>63 212 320 282</bbox>、<bbox>178 714 826 810</bbox>、<bbox>814 819 949 894</bbox>、<bbox>326 824 669 930</bbox>；1 只鹦鹉：<bbox>347 305 642 997</bbox>。",
    "image": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream_50_pro_layer_input.png",
    "layer_decomposition": true,
    "size": "2K",
    "output_format": "jpeg",
    "response_format": "url",
    "watermark": true
}
```


### 响应结果说明

图层拆分模式下，响应参数 `data` 数组会同时返回底图和所有图层。您可通过 `url` 下载所有输出图，并根据图层叠放顺序（`z_index`）区分底图和图层。利用图层的边界框坐标信息（`bounding_box`）和图层叠放顺序（`z_index`）可还原、编辑或重组图层。


<span aceTableMode="list" aceTableWidth="2,2,5"></span>
|字段 |返回对象 |含义 |
|---|---|---|
|`url` |底图、图层 |底图或图层的下载链接。图片 URL 仅保留 24 小时。 |
|`z_index` |底图、图层 |图层叠放顺序。底图 `z_index` 固定为 `0`，各图层按 `z_index` 递增排序。 |
|`bounding_box.absolute` |图层 |图层在输出底图坐标系中的绝对像素位置，适用于将图层还原到输出底图的原始位置。 |
|`bounding_box.normalized` |图层 |图层在输出底图坐标系中的归一化位置，适用于将图层还原到任意尺寸的自定义画布。 |
|`name`、`description` |图层 |图层名称和内容描述。 |


**返回结构示例：** 

```JSON
{
    "model": "doubao-seedream-5-0-pro-260628",
    "created": 1784696685,
    "data": [
        {
            "url": "https://...",
            "size": "2048x2048",
            "output_format": "jpeg",
            "z_index": 0
        },
        {
            "url": "https://...",
            "size": "1273x265",
            "output_format": "png",
            "z_index": 1,
            "bounding_box": {
                "absolute": [383, 120, 1655, 384],
                "normalized": [187, 59, 808, 188]
            },
            "name": "Seedream标题文字",
            "description": "黄色大号衬线字体的Seedream标题文字"
        }
    ],
    "usage": {
        "input_images": 1,
        "generated_images": 8,
        "output_tokens": 23107,
        "total_tokens": 23107
    }
}
```


<span id=".5L2_55So5ouG5YiG5ZCO55qE5Zu-5bGC"></span>
## 使用拆分后的图层

获取底图和图层后，可以直接按原位置还原图层，也可以调整图层位置、大小和叠放顺序；如果需要修改某个元素的颜色、风格或细节，也可以单独编辑该图层。

还原或重组图层时，可按以下顺序处理响应结果：


* 将 `data` 数组中 `z_index` 为 `0` 的对象作为画布背景。

* 提取 `z_index` 大于 `0` 的图层对象，并按 `z_index` 从小到大排序。

* 下载图层 PNG，并根据 `bounding_box` 将图层放置到输出底图或目标画布。

<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">说明</div>


<div data-tips="true" data-tips-type="tip">使用 <code>bounding_box.absolute</code> 可将输出图层还原到其在输出底图坐标系中的边界框区域；使用 <code>bounding_box.normalized</code> 可将输出图层还原到目标画布中的边界框区域。归一化坐标为整数，换算后可能存在取整误差。</div>


# 提示词优化模式

Seedream 5.0 pro 支持通过 `optimize_prompt_options.mode` 参数控制提示词优化的模式：


* `standard`（默认值）：标准模式，生成内容的质量更高，耗时较长。

* `fast`：快速模式，生成内容的耗时更短，效果略低于标准模式；**Seedream 5.0 flash / lite / 4.5 当前不支持**（5.0 pro 支持）。


<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">建议</div>


<div data-tips="true" data-tips-type="tip">如您的业务对生成时延较为敏感，推荐使用 Seedream 5.0 pro 的 <code>fast</code> 模式，或使用 Seedream 5.0 flash 以获得更快的图片生成速度。</div>


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

* **background** ：指定是否生成带透明通道的图片。

* **watermark** ：指定是否为输出图片添加水印。


<span id=".5Zu-5YOP6L6T5Ye65bC65a-4"></span>
### 图像输出尺寸

支持以下尺寸设置方式，不可混用。

**方式 1：指定分辨率档位（推荐）** 

在 prompt 中用自然语言描述图片宽高比、图片形状或图片用途，最终由模型判断生成图片的大小。


* 默认值：`2K`

* 可选值：`1K`、`1.5K`、`2K`

<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">价格说明</div>


<div data-tips="true" data-tips-type="tip">`1.5K` 与 `1K` 价格相同，且图片生成效果更优。</div>


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
|1.5K |1:1 |1536x1536 |
||4:3 |1792x1344 |
||3:4 |1344x1792 |
||16:9 |2048x1152 |
||9:16 |1152x2048 |
||3:2 |1872x1248 |
||2:3 |1248x1872 |
||21:9 |2352x1008 |
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


**Seedream 5.0 pro（图层拆分场景）** 

仅支持通过指定分辨率档位的方式设置。输出图的分辨率规则如下：


* **底图**：输出底图的分辨率和 `size` 指定的分辨率一致；输出底图和原待拆分图的宽高比一致。

* **各图层**：输出图层的分辨率和 `size` 指定的分辨率接近；每个输出图层和其在原图中的宽高比一致。


`size` 的默认值与可选值：


* 默认值：`auto`

* 可选值：`1K`、`1.5K`、`2K`、`auto`（根据输入图的尺寸和宽高比进行输出）


<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">auto 适配规则</div>


<div data-tips="true" data-tips-type="tip">auto 模式下，模型将根据输入图片中底图和每个图层的原始尺寸进行输出：<br><br>* 若输入图片中底图和每个图层的原始尺寸在 [<code>1280x720</code>（921600）, <code>2048x2048x1.1025</code>（4624220）] 之间，按照原尺寸输出底图与每个图层；且各自保持其在原图中的宽高比。<br>* 若输入图片中底图和每个图层的原始尺寸小于 1K，按 1K 输出底图与每个图层；且各自保持其在原图中的宽高比。<br>* 若输入图片中底图和每个图层的原始尺寸大于 2K，按 2K 输出底图与每个图层；且各自保持其在原图中的宽高比。</div>


<span id=".5Zu-5YOP6L6T5Ye65pa55byP"></span>
### 图像输出方式

通过设置 **response_format** 参数，可以指定生成图像的返回方式：


* `url`（默认值）：返回图片下载链接，**链接在图片生成后 24 小时内有效，请及时下载图片**。

* `b64_json`：以 Base64 编码字符串的 JSON 格式返回图像数据。


```JSON
{
    "response_format": "url"
}
```


<span id=".5Zu-5YOP5paH5Lu25qC85byP"></span>
### 图像文件格式

通过设置 **output_format** 参数，指定生成图像文件的格式（**默认值 `jpeg`**）：


* `png`

* `jpeg`


```JSON
{
    "output_format": "png"
}
```


<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">注意</div>


<div data-tips="true" data-tips-type="warning">图层拆分场景下，<code>output_format</code> 仅控制底图的输出格式，图层始终以 <code>png</code> 格式输出。</div>


<span id=".5Zu-5YOP6YCP5pi-6YCa6YGT6K6-572u"></span>
### 透明通道设置

设置 **background** 参数，控制是否生成带透明通道的图片：


* `transparent`：透明背景模式，输出带有透明背景的图。

* `opaque`（默认）：不透明背景模式，生成常规的实体背景图。


```JSON
{
    "background": "transparent"
}
```


<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">使用限制</div>


<div data-tips="true" data-tips-type="warning">* 仅支持图生图场景，且只支持输入 <strong>1 张带透明通道</strong>的图片；<br>* 透明背景模式下，输出图片默认为 <code>png</code> 格式，若同时配置 <code>output_format</code> 为 <code>jpeg</code>，将触发报错；<br>* 若传入了不支持透明通道的文件格式（如 <code>jpeg</code>），将触发报错。</div>


<span id=".5Zu-5YOP5Lit5re75Yqg5rC05Y2w"></span>
### 图像中添加水印

通过设置 **watermark** 参数，来控制是否在生成的图片中添加水印（**默认值 `true`**，即不传该参数会在右下角添加"AI 生成"水印）。


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

不同场景对输入图的约束不同，详见下表：


<span aceTableMode="list" aceTableWidth="1.5,3,3"></span>
|约束项 |图片生成场景 |图层拆分场景 |
|---|---|---|
|图片格式 |jpeg、png、webp、bmp、tiff、gif、heic、heif |png、jpeg |
|总像素（宽×高） |[196, `6000×6000`（3600万）] |[`512×512`（262144）, `6000×6000`（3600万）] |
|宽高长度（px） |大于 14 |— |
|宽高比（宽/高） |[1/16, 16] |[1/16, 16] |
|大小 |不超过 30 MB |不超过 30 MB |
|传入张数 |最多传入 10 张参考图 |仅支持传入单张图 |


<div data-tips="true" data-tips-type="tip" data-tips-is-title="true">说明</div>


<div data-tips="true" data-tips-type="tip">总像素是对单张图宽度和高度的<strong>像素乘积</strong>限制，而不是对宽度或高度的单独值进行限制。</div>


**保存时间**

图片URL仅保留24小时，超时后会被自动清除。请您务必及时保存生成的图片。

**限流说明**


* IPM 限流：账号下同模型（区分模型版本）每分钟生成图片数量上限。若超过该限制，生成图片时会报错。

   * 图层拆分场景下，每次请求预扣减 17 IPM（即按最大输出张数 17 张预留配额）；图片全部生成后，按实际生成数量返还多扣减的额度。

* 不同模型的限制值不同，详见 [图片生成能力](https://www.volcengine.com/docs/82379/1330310#d3e5e0eb)。




