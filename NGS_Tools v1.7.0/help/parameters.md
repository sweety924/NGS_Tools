# 参数介绍
该文档摘录并翻译了[CRISPResso2](https://github.com/pinellolab/CRISPResso2)
主页里的**部分内容**以及bcl2fastq帮助文档的**部分内容**，供你自己分析的时候自主选择合适参数使用。

# 目录
[CRISPResso2](#CRISPResso2)

[bcl2fastq](#bcl2fastq)





# CRISPResso2
本部分只翻译了部分我认为你可能会用到的参数！！

[CRISPResso2项目主页文档](https://github.com/pinellolab/CRISPResso2)

## 质控参数

 ### --min_average_read_quality：
 单个扩增序列的测序结果的的最低平均质量分数 (phred33)（默认值：10）


| 分数  | 含义                |
|-----|-------------------|
| 10  | 该测序的正确率为 90%      |
| 20  | 该测序的正确率为 99%      |
| 30  | 该测序的正确率为 99.9%    |
| 40  | 该测序的正确率为 99.99%   |
| 50  | 该测序的正确率为 99.999%  |
| 60  | 该测序的正确率为 99.9999% |

### --min_single_bp_quality：
单个扩增序列的测序内，单个碱基的最低分数 (phred33)（默认值：0）。如果某个扩增序列内有碱基的分数低于该分数，
该扩增序列的结果舍弃不用。（默认：0）

### --min_bp_quality_or_N: 
质量分数 (phred33) 小于此值的碱基将被设置为“N”（默认值：0）


## 分析窗口设置
### 关于分析窗口：
虽然CRISPResso2会分析整个参考序列上的编辑情况，但是只有分析窗口中的内容是纳入统计的。窗口过大可能将测序文件边缘的低质量结果纳入分析，造成indel
比例偏高；过小可能会忽略部分indel。

### --quantification_window_center：
指定分析窗口的中心。在提供的 sgRNA 序列的 3' 端开始数。请记住，必须在没有 PAM 的情况下输入 sgRNA 序列。对于切割核酸酶，这是预测的切割位置。
默认为-3，适用于Cas9系统。例如：
```
--quantification_window_center -3
```

对于其他核酸酶，应当使用其他切割偏移例如，例如使用 Cpf1，则此参数将设置为 1。
```
--quantification_window_center 1
```
**对于碱基编辑器，本工具已经自动填写，无需你设置！！！
在BE中，本工具会自动以sgRNA的中心为分析窗口中心，千万不要再设置该参数！HDR、PE、NHEJ你可以修改该参数。**


### --quantification_window_size：
以“--quantification_window_center”参数指定的位置为中心，向3和5端延伸的量化窗口的大小（以 bp 为单位）

例如，该值输入3，那么窗口就是分析中心上游3bp加下游3bp，实际分析的时候就将这6bp内的信息纳入统计。

**对于碱基编辑器，本工具已经自动填写，无需你设置！！！
在BE中，本工具会自动以sgRNA的中心为分析窗口中心，窗口只包含sgRNA。千万不要再设置该参数！HDR、PE、NHEJ你可以修改该参数，BE就不要改了。**

### --ignore_substitutions：
忽略分析窗口内的碱基替换事件（默认值：False）

### --ignore_insertions：
忽略分析窗口内的插入事件（默认值：False）

### --ignore_deletions：
忽略分析窗口内的删除事件（默认值：False）

### --discard_indel_reads：
从分析中忽略分析窗口内的有插入缺失的测序结果（默认值：False）


## 比对参数

### --amplicon_min_alignment_score：
扩增子最小比对分数；得分在 0 到 100 之间；
单个测序结果与参考序列比对后，同源性计算为它们共有的 bp 数。

如果比对上的测序结果具有小于此参数的同源性，则将其丢弃。
 （默认值：60）

-------

# bcl2fastq
本部分只翻译了部分我认为你可能会用到的参数！！

[illumina官方文档](https://support.illumina.com/sequencing/sequencing_software/bcl2fastq-conversion-software.html)

bcl2fastq --help 获取以下参数文档：
```commandline
  -r 或者 --loading-threads               加载bcl文件的线程数。默认为4
  -p 或者 --processing-threads            根据index拆分样品的线程数。默认为1
  -w 或者 --writing-threads               拆分好的样品的写入到fastq文件的线程数。默认为4
  --minimum-trimmed-read-length          adapter trimming后允许剩下的序列长度。小于该长度的会被舍弃。默认35
  --no-bgzf-compression                  拆分出来的fastq文件不压缩，直接输出fastq文件而不是fastq.gz。不推荐使用该参数，该参数会增大硬盘空间占用
  --fastq-compression-level arg (=4)     fastq文件压缩率。默认4，最大9
  --barcode-mismatches arg (=1)          每个index允许的最小错配数。默认0
  --no-lane-splitting                    do not split fastq files by lane.
```
