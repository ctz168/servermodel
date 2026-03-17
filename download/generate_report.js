const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, 
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType, 
        ShadingType, VerticalAlign, PageNumber, LevelFormat } = require('docx');
const fs = require('fs');

// 颜色配置 - 使用 "Midnight Code" 配色
const colors = {
    primary: "020617",      // Midnight Black
    body: "1E293B",         // Deep Slate Blue
    secondary: "64748B",    // Cool Blue-Gray
    accent: "94A3B8",       // Steady Silver
    tableBg: "F8FAFC",      // Glacial Blue-White
};

// 表格边框样式
const tableBorder = { style: BorderStyle.SINGLE, size: 1, color: colors.secondary };
const cellBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder };

// 创建文档
const doc = new Document({
    styles: {
        default: { 
            document: { 
                run: { font: "SimSun", size: 24 } 
            } 
        },
        paragraphStyles: [
            { 
                id: "Title", 
                name: "Title", 
                basedOn: "Normal",
                run: { size: 44, bold: true, color: colors.primary, font: "SimHei" },
                paragraph: { spacing: { before: 240, after: 120 }, alignment: AlignmentType.CENTER } 
            },
            { 
                id: "Heading1", 
                name: "Heading 1", 
                basedOn: "Normal", 
                next: "Normal", 
                quickFormat: true,
                run: { size: 32, bold: true, color: colors.primary, font: "SimHei" },
                paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } 
            },
            { 
                id: "Heading2", 
                name: "Heading 2", 
                basedOn: "Normal", 
                next: "Normal", 
                quickFormat: true,
                run: { size: 28, bold: true, color: colors.primary, font: "SimHei" },
                paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } 
            },
        ]
    },
    numbering: {
        config: [
            {
                reference: "bullet-list",
                levels: [{
                    level: 0,
                    format: LevelFormat.BULLET,
                    text: "\u2022",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } }
                }]
            },
            {
                reference: "numbered-list-1",
                levels: [{
                    level: 0,
                    format: LevelFormat.DECIMAL,
                    text: "%1.",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } }
                }]
            },
            {
                reference: "numbered-list-2",
                levels: [{
                    level: 0,
                    format: LevelFormat.DECIMAL,
                    text: "%1.",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } }
                }]
            }
        ]
    },
    sections: [{
        properties: {
            page: {
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({ text: "\u5206\u5e03\u5f0f\u5927\u6a21\u578b\u63a8\u7406\u7cfb\u7edf - \u5206\u6790\u62a5\u544a", font: "SimSun", size: 18, color: colors.secondary })]
                })]
            })
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: "\u7b2c ", font: "SimSun", size: 18 }),
                        new TextRun({ children: [PageNumber.CURRENT], font: "SimSun", size: 18 }),
                        new TextRun({ text: " \u9875", font: "SimSun", size: 18 })
                    ]
                })]
            })
        },
        children: [
            // 标题
            new Paragraph({
                heading: HeadingLevel.TITLE,
                children: [new TextRun({ text: "\u5206\u5e03\u5f0f\u5927\u6a21\u578b\u63a8\u7406\u7cfb\u7edf", font: "SimHei" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 480 },
                children: [new TextRun({ text: "\u4ee3\u7801\u5206\u6790\u4e0e\u5b8c\u5584\u62a5\u544a", font: "SimHei", size: 28, color: colors.secondary })]
            }),
            
            // 第一章：项目概述
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u4e00\u3001\u9879\u76ee\u6982\u8ff0", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u672c\u9879\u76ee\u662f\u4e00\u4e2a\u5206\u5e03\u5f0f\u5927\u6a21\u578b\u63a8\u7406\u7cfb\u7edf\uff0c\u652f\u6301\u591a\u8282\u70b9\u534f\u540c\u63a8\u7406\u3002\u9879\u76ee\u4f4d\u4e8e GitHub \u4ed3\u5e93 ctz168/servermodel \u7684 glm \u5206\u652f\uff0c\u5305\u542b\u591a\u79cd\u8fd0\u884c\u6a21\u5f0f\u3002\u672c\u6b21\u5206\u6790\u7684\u76ee\u7684\u662f\u8bc6\u522b\u672a\u5b9e\u73b0\u7684\u529f\u80fd\uff0c\u5e76\u6839\u636e\u7528\u6237\u9700\u6c42\u8fdb\u884c\u5b8c\u5584\uff0c\u6700\u7ec8\u5b9e\u73b0\u4e00\u4e2a\u7edf\u4e00\u7684\u53bb\u4e2d\u5fc3\u5316\u5206\u5e03\u5f0f\u7b97\u529b\u7cfb\u7edf\u3002", font: "SimSun" })]
            }),
            
            // 第二章：现有模式分析
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u4e8c\u3001\u73b0\u6709\u6a21\u5f0f\u5206\u6790", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u9879\u76ee\u5f53\u524d\u5305\u542b\u4e94\u79cd\u8fd0\u884c\u6a21\u5f0f\uff0c\u5404\u6a21\u5f0f\u7684\u5b9e\u73b0\u72b6\u6001\u5982\u4e0b\uff1a", font: "SimSun" })]
            }),
            
            // 模式对比表格
            new Table({
                columnWidths: [2500, 3000, 1500, 2360],
                rows: [
                    new TableRow({
                        tableHeader: true,
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u6a21\u5f0f\u540d\u79f0", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u6587\u4ef6", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u5b9e\u73b0\u7a0b\u5ea6", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u8bf4\u660e", bold: true, font: "SimHei", size: 22 })] })]
                            })
                        ]
                    }),
                    // 数据行
                    ...createTableRows([
                        ["\u7edf\u4e00\u53bb\u4e2d\u5fc3\u5316\u6a21\u5f0f", "node_unified.py", "80%", "\u6700\u5b8c\u6574\u7684\u5b9e\u73b0"],
                        ["\u8d44\u6e90\u611f\u77e5\u6a21\u5f0f", "node_resource_aware.py", "90%", "\u5b8c\u6574\u5b9e\u73b0\u8d44\u6e90\u68c0\u6d4b"],
                        ["Pipeline\u5e76\u884c\u6a21\u5f0f", "node_pipeline_shard.py", "70%", "\u57fa\u672c\u5b9e\u73b0\u6a21\u578b\u5206\u7247"],
                        ["\u53bb\u4e2d\u5fc3\u5316\u6a21\u5f0f", "node_decentralized.py", "75%", "\u5b9e\u73b0\u4e86Raft\u5171\u8bc6"],
                        ["\u751f\u4ea7\u7ea7\u8282\u70b9", "node_service_production.py", "95%", "\u9700\u8981\u4e2d\u592e\u670d\u52a1\u5668"]
                    ])
                ]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 120, after: 240 },
                children: [new TextRun({ text: "\u8868 1\uff1a\u73b0\u6709\u6a21\u5f0f\u5b9e\u73b0\u72b6\u6001\u5bf9\u6bd4", font: "SimSun", size: 20, color: colors.secondary })]
            }),
            
            // 第三章：用户需求分析
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u4e09\u3001\u7528\u6237\u9700\u6c42\u5206\u6790", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u6839\u636e\u7528\u6237\u63cf\u8ff0\uff0c\u7cfb\u7edf\u9700\u8981\u5b9e\u73b0\u4ee5\u4e0b\u6838\u5fc3\u529f\u80fd\uff1a", font: "SimSun" })]
            }),
            
            // 需求列表
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u4efb\u610f\u8282\u70b9\u542f\u52a8\u540e\u81ea\u52a8\u68c0\u67e5\u662f\u5426\u6709\u5176\u4ed6\u8282\u70b9\u5b58\u5728", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u5982\u679c\u6ca1\u6709\u8282\u70b9\u5b58\u5728\uff0c\u81ea\u52a8\u6210\u4e3a\u9886\u5bfc\u8282\u70b9\uff08\u540c\u65f6\u4e5f\u662f\u5de5\u4f5c\u8282\u70b9\uff09", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u9886\u5bfc\u8282\u70b9\u8d1f\u8d23\uff1a\u8d44\u6e90\u5206\u914d\u3001API\u7edf\u4e00\u5165\u53e3\u3001\u4efb\u52a1\u8c03\u5ea6", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u65b0\u8282\u70b9\u81ea\u52a8\u52a0\u5165\u96c6\u7fa4", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u5206\u5e03\u5f0f\u9009\u4e3e\u51b3\u5b9a\u9886\u5bfc\u4e2d\u5fc3", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u8054\u5408\u5206\u5e03\u5f0f\u63a8\u7406", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "numbered-list-1", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u6700\u7ec8\u5408\u6210\u53ea\u6709\u4e00\u4e2a\u6a21\u5f0f", font: "SimSun" })]
            }),
            
            // 第四章：完善方案
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u56db\u3001\u5b8c\u5584\u65b9\u6848", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u57fa\u4e8e\u4ee5\u4e0a\u5206\u6790\uff0c\u6211\u4eec\u521b\u5efa\u4e86\u4e00\u4e2a\u7edf\u4e00\u7684\u751f\u4ea7\u7ea7\u8282\u70b9\u670d\u52a1\u6587\u4ef6 node_unified_production.py\uff0c\u6574\u5408\u4e86\u6240\u6709\u6a21\u5f0f\u7684\u4f18\u70b9\u3002\u4e3b\u8981\u5b9e\u73b0\u5305\u62ec\uff1a", font: "SimSun" })]
            }),
            
            // 4.1 自动节点发现
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "4.1 \u81ea\u52a8\u8282\u70b9\u53d1\u73b0", font: "SimHei" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "UDP\u5e7f\u64ad\u53d1\u73b0\uff1a\u81ea\u52a8\u53d1\u73b0\u540c\u4e00\u7f51\u7edc\u4e2d\u7684\u8282\u70b9", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u79cd\u5b50\u8282\u70b9\u8fde\u63a5\uff1a\u652f\u6301\u914d\u7f6e\u79cd\u5b50\u8282\u70b9\u8fdb\u884c\u53d1\u73b0", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u53cc\u91cd\u53d1\u73b0\u673a\u5236\uff1a\u786e\u4fdd\u8282\u70b9\u80fd\u591f\u53ef\u9760\u5730\u52a0\u5165\u96c6\u7fa4", font: "SimSun" })]
            }),
            
            // 4.2 Raft选举协议
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "4.2 Raft\u9009\u4e3e\u534f\u8bae", font: "SimHei" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u5b8c\u6574\u7684\u9886\u5bfc\u8005\u9009\u4e3e\u6d41\u7a0b", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u5fc3\u8df3\u7ef4\u62a4\u673a\u5236", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u6545\u969c\u81ea\u52a8\u8f6c\u79fb", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u591a\u6570\u7968\u51b3\u673a\u5236", font: "SimSun" })]
            }),
            
            // 4.3 领导节点功能
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "4.3 \u9886\u5bfc\u8282\u70b9\u529f\u80fd", font: "SimHei" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u7edf\u4e00REST API\u5165\u53e3", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u667a\u80fd\u4efb\u52a1\u8c03\u5ea6", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u8d44\u6e90\u611f\u77e5\u5206\u914d", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u8d1f\u8f7d\u5747\u8861", font: "SimSun" })]
            }),
            
            // 4.4 分布式推理
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "4.4 \u5206\u5e03\u5f0f\u63a8\u7406", font: "SimHei" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u6570\u636e\u5e76\u884c\u652f\u6301", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "Pipeline\u5e76\u884c\u6846\u67b6", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u5206\u7247\u7ba1\u7406", font: "SimSun" })]
            }),
            new Paragraph({
                numbering: { reference: "bullet-list", level: 0 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u534f\u8c03\u673a\u5236", font: "SimSun" })]
            }),
            
            // 第五章：新增文件
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u4e94\u3001\u65b0\u589e\u6587\u4ef6", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u672c\u6b21\u5b8c\u5584\u65b0\u589e\u4e86\u4ee5\u4e0b\u6587\u4ef6\uff1a", font: "SimSun" })]
            }),
            
            // 新增文件表格
            new Table({
                columnWidths: [4000, 5360],
                rows: [
                    new TableRow({
                        tableHeader: true,
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u6587\u4ef6\u8def\u5f84", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u8bf4\u660e", bold: true, font: "SimHei", size: 22 })] })]
                            })
                        ]
                    }),
                    ...createFileTableRows([
                        ["download/node_unified_production.py", "\u7edf\u4e00\u751f\u4ea7\u7ea7\u8282\u70b9\u670d\u52a1\uff08\u7ea61500\u884c\uff09"],
                        ["scripts/start_unified_production.sh", "\u542f\u52a8\u811a\u672c"],
                        ["scripts/stop_unified_production.sh", "\u505c\u6b62\u811a\u672c"],
                        ["config/unified_config.json", "\u914d\u7f6e\u6587\u4ef6\u6a21\u677f"]
                    ])
                ]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 120, after: 240 },
                children: [new TextRun({ text: "\u8868 2\uff1a\u65b0\u589e\u6587\u4ef6\u5217\u8868", font: "SimSun", size: 20, color: colors.secondary })]
            }),
            
            // 第六章：REST API
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u516d\u3001REST API \u63a5\u53e3", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u7edf\u4e00\u8282\u70b9\u670d\u52a1\u63d0\u4f9b\u4ee5\u4e0b REST API \u63a5\u53e3\uff1a", font: "SimSun" })]
            }),
            
            // API表格
            new Table({
                columnWidths: [2000, 3000, 4360],
                rows: [
                    new TableRow({
                        tableHeader: true,
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u65b9\u6cd5", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u8def\u5f84", bold: true, font: "SimHei", size: 22 })] })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: colors.tableBg, type: ShadingType.CLEAR },
                                verticalAlign: VerticalAlign.CENTER,
                                children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u8bf4\u660e", bold: true, font: "SimHei", size: 22 })] })]
                            })
                        ]
                    }),
                    ...createApiTableRows([
                        ["GET", "/health", "\u5065\u5eb7\u68c0\u67e5"],
                        ["GET", "/status", "\u8282\u70b9\u72b6\u6001"],
                        ["GET", "/nodes", "\u8282\u70b9\u5217\u8868"],
                        ["POST", "/inference", "\u63a8\u7406\u8bf7\u6c42"],
                        ["POST", "/task", "\u4efb\u52a1\u63d0\u4ea4"],
                        ["GET", "/task/status", "\u4efb\u52a1\u72b6\u6001"],
                        ["GET", "/stats", "\u7edf\u8ba1\u4fe1\u606f"]
                    ])
                ]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 120, after: 240 },
                children: [new TextRun({ text: "\u8868 3\uff1aREST API \u63a5\u53e3\u5217\u8868", font: "SimSun", size: 20, color: colors.secondary })]
            }),
            
            // 第七章：使用示例
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u4e03\u3001\u4f7f\u7528\u793a\u4f8b", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u4ee5\u4e0b\u662f\u7edf\u4e00\u8282\u70b9\u670d\u52a1\u7684\u4f7f\u7528\u793a\u4f8b\uff1a", font: "SimSun" })]
            }),
            
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "7.1 \u542f\u52a8\u7b2c\u4e00\u4e2a\u8282\u70b9\uff08\u81ea\u52a8\u6210\u4e3a\u9886\u5bfc\uff09", font: "SimHei" })]
            }),
            new Paragraph({
                spacing: { line: 360 },
                children: [new TextRun({ text: "python node_unified_production.py --port 5000 --api-port 8080", font: "SarasaMonoSC", size: 20 })]
            }),
            
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "7.2 \u542f\u52a8\u540e\u7eed\u8282\u70b9\uff08\u81ea\u52a8\u53d1\u73b0\u5e76\u52a0\u5165\uff09", font: "SimHei" })]
            }),
            new Paragraph({
                spacing: { line: 360 },
                children: [new TextRun({ text: "python node_unified_production.py --port 5001 --seeds \"localhost:5000\"", font: "SarasaMonoSC", size: 20 })]
            }),
            
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun({ text: "7.3 \u53d1\u9001\u63a8\u7406\u8bf7\u6c42", font: "SimHei" })]
            }),
            new Paragraph({
                spacing: { line: 360 },
                children: [new TextRun({ text: "curl -X POST http://localhost:8080/inference -H 'Content-Type: application/json' -d '{\"prompt\": \"\u4f60\u597d\"}'", font: "SarasaMonoSC", size: 20 })]
            }),
            
            // 第八章：总结
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: "\u516b\u3001\u603b\u7ed3", font: "SimHei" })]
            }),
            new Paragraph({
                indent: { firstLine: 480 },
                spacing: { line: 360 },
                children: [new TextRun({ text: "\u672c\u6b21\u5206\u6790\u548c\u5b8c\u5584\u5de5\u4f5c\u6210\u529f\u5b9e\u73b0\u4e86\u7528\u6237\u9700\u6c42\u7684\u6838\u5fc3\u529f\u80fd\uff0c\u521b\u5efa\u4e86\u4e00\u4e2a\u7edf\u4e00\u7684\u53bb\u4e2d\u5fc3\u5316\u5206\u5e03\u5f0f\u7b97\u529b\u7cfb\u7edf\u3002\u7cfb\u7edf\u652f\u6301\u81ea\u52a8\u8282\u70b9\u53d1\u73b0\u3001Raft\u9009\u4e3e\u3001\u7edf\u4e00API\u3001\u5206\u5e03\u5f0f\u63a8\u7406\u7b49\u6838\u5fc3\u7279\u6027\uff0c\u8fbe\u5230\u4e86\u751f\u4ea7\u7ea7\u7684\u5b9e\u73b0\u6c34\u5e73\u3002", font: "SimSun" })]
            }),
        ]
    }]
});

// 辅助函数：创建表格数据行
function createTableRows(data) {
    return data.map(row => new TableRow({
        children: row.map(cell => new TableCell({
            borders: cellBorders,
            verticalAlign: VerticalAlign.CENTER,
            children: [new Paragraph({ 
                alignment: AlignmentType.CENTER, 
                children: [new TextRun({ text: cell, font: "SimSun", size: 22 })] 
            })]
        }))
    }));
}

// 辅助函数：创建文件表格行
function createFileTableRows(data) {
    return data.map(row => new TableRow({
        children: [
            new TableCell({
                borders: cellBorders,
                verticalAlign: VerticalAlign.CENTER,
                children: [new Paragraph({ 
                    children: [new TextRun({ text: row[0], font: "SarasaMonoSC", size: 20 })] 
                })]
            }),
            new TableCell({
                borders: cellBorders,
                verticalAlign: VerticalAlign.CENTER,
                children: [new Paragraph({ 
                    children: [new TextRun({ text: row[1], font: "SimSun", size: 22 })] 
                })]
            })
        ]
    }));
}

// 辅助函数：创建API表格行
function createApiTableRows(data) {
    return data.map(row => new TableRow({
        children: [
            new TableCell({
                borders: cellBorders,
                verticalAlign: VerticalAlign.CENTER,
                children: [new Paragraph({ 
                    alignment: AlignmentType.CENTER,
                    children: [new TextRun({ text: row[0], font: "SarasaMonoSC", size: 20, bold: row[0] === "POST" })] 
                })]
            }),
            new TableCell({
                borders: cellBorders,
                verticalAlign: VerticalAlign.CENTER,
                children: [new Paragraph({ 
                    children: [new TextRun({ text: row[1], font: "SarasaMonoSC", size: 20 })] 
                })]
            }),
            new TableCell({
                borders: cellBorders,
                verticalAlign: VerticalAlign.CENTER,
                children: [new Paragraph({ 
                    children: [new TextRun({ text: row[2], font: "SimSun", size: 22 })] 
                })]
            })
        ]
    }));
}

// 保存文档
Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync("/home/z/my-project/download/分布式大模型推理系统分析报告.docx", buffer);
    console.log("文档已生成: /home/z/my-project/download/分布式大模型推理系统分析报告.docx");
});
