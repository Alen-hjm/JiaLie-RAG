"""写入虚构演示简历。

这批数据有两个用途：
  1) 现场演示：让"输入一句 JD -> 返回候选人排序"有足够多的候选人可看；
  2) 评测：``eval/gold.json`` 的黄金集需要一定规模的语料，否则 Recall@K / NDCG
     会恒等于 1，指标没有区分度。当前语料为 16 位虚构候选人（覆盖半导体/集成
     电路/新能源/医疗/互联网/制造业 × 销售总监/销售经理/区域经理/大客户经理/
     销售工程师/财务总监 × 上海/苏州/无锡/深圳/北京/杭州/南京/广州）。

刻意保持虚构：不含任何真实个人信息，避免把真实简历送进云端模型服务。

用法：
    cd backend
    .venv\\Scripts\\python -m scripts.seed_demo
重复执行是幂等的（按文件名与 SHA-256 双重去重）。
"""

import argparse
import hashlib

from docx import Document
from sqlalchemy import select

from app.bootstrap import bootstrap
from app.config import get_settings
from app.db import SessionLocal
from app.models import ImportTask, ResumeDocument
from app.services.ingestion import process_document

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

SAMPLES: dict[str, list[str]] = {
    # ---------- 半导体 / 集成电路（销售主线，黄金集的主要目标） ----------
    "林若川_半导体销售总监.docx": [
        "林若川", "上海 | 13800000001 | lin.demo@example.com", "现任职位：销售总监",
        "12 年半导体设备与材料销售经验，负责华东区域晶圆厂大客户。",
        "工作经历", "2018-至今 华芯设备 销售总监", "管理 18 人销售团队，建立渠道管理体系。2024 年销售额 1.2 亿元，同比增长 36%。",
        "熟悉晶圆厂客户开发、封装测试、CRM 与销售管理。",
    ],
    "周启明_区域销售经理.docx": [
        "周启明", "苏州 | 13800000002 | zhou.demo@example.com", "现任职位：区域经理",
        "8 年集成电路材料销售经验，覆盖华东客户。", "工作经历", "2020-至今 纳微材料 区域销售经理",
        "负责苏沪区域大客户和渠道管理，带领 6 人团队，年度业绩 4500 万元。", "熟悉大客户、CRM、英语商务沟通。",
    ],
    "蒋子恒_半导体销售总监.docx": [
        "蒋子恒", "苏州 | 13800000011 | jiang.demo@example.com", "现任职位：销售总监",
        "13 年半导体领域销售经验，长期服务晶圆厂与封装测试客户。",
        "工作经历", "2016-至今 芯越科技 销售总监", "带 22 人团队，年度销售额 2.1 亿元，连续三年增长超过 25%。",
        "熟悉晶圆厂、封装测试、大客户、销售管理与渠道管理。",
    ],
    "苏文卿_半导体销售经理.docx": [
        "苏文卿", "无锡 | 13800000005 | su.demo@example.com", "现任职位：销售经理",
        "9 年半导体设备销售经验，负责华东晶圆厂客户开发。",
        "工作经历", "2019-至今 卓芯半导体 销售经理", "管理 7 人团队，年度业绩 7800 万元。",
        "熟悉晶圆厂、封装测试、销售管理与 CRM。",
    ],
    "崔亦帆_大客户经理.docx": [
        "崔亦帆", "无锡 | 13800000015 | cui.demo@example.com", "现任职位：大客户经理",
        "6 年半导体材料销售经验，专注晶圆厂大客户维护。",
        "工作经历", "2022-至今 恒晶材料 大客户经理", "负责 12 家晶圆厂客户，年度业绩 3600 万元。",
        "熟悉大客户、晶圆厂与 CRM。",
    ],
    "郑天华_集成电路大客户经理.docx": [
        "郑天华", "北京 | 13800000007 | zheng.demo@example.com", "现任职位：大客户经理",
        "7 年集成电路销售经验，覆盖华北客户。",
        "工作经历", "2021-至今 北方微电子 大客户经理", "负责集成电路客户开发与维护，年度业绩 5200 万元。",
        "熟悉大客户、CRM 与英语商务沟通。",
    ],
    # ---------- 新能源 / 医疗 / 互联网 / 制造业 ----------
    "陈星野_新能源销售经理.docx": [
        "陈星野", "杭州 | 13800000003 | chen.demo@example.com", "现任职位：销售经理",
        "10 年新能源设备销售经验。", "工作经历", "2019-至今 绿能科技 销售经理",
        "管理 10 人团队，负责渠道管理，年度销售额 6000 万元。", "擅长销售管理、项目管理与 CRM。",
    ],
    "汪静涛_新能源销售经理.docx": [
        "汪静涛", "上海 | 13800000012 | wang.demo@example.com", "现任职位：销售经理",
        "5 年新能源材料销售经验，负责华东区域客户。",
        "工作经历", "2023-至今 旭能材料 销售经理", "年度业绩 2800 万元，客户复购率提升明显。",
        "熟悉 CRM 与项目管理。",
    ],
    "罗启帆_医疗器械销售经理.docx": [
        "罗启帆", "南京 | 13800000009 | luo.demo@example.com", "现任职位：销售经理",
        "11 年医疗设备销售经验，覆盖华东医院渠道。",
        "工作经历", "2018-至今 康明医疗 销售经理", "管理 9 人团队，负责渠道管理，年度业绩 6400 万元。",
        "熟悉渠道管理、团队管理与项目管理。",
    ],
    "何佳琪_互联网区域经理.docx": [
        "何佳琪", "深圳 | 13800000010 | he.demo@example.com", "现任职位：区域经理",
        "6 年互联网行业销售经验，负责华南中小客户。",
        "工作经历", "2022-至今 云图科技 区域经理", "年度业绩 1900 万元，客户续约率 82%。",
        "熟悉项目管理、CRM 与英语商务沟通。",
    ],
    "卢承恩_互联网销售总监.docx": [
        "卢承恩", "北京 | 13800000014 | lu.demo@example.com", "现任职位：销售总监",
        "9 年互联网行业销售经验，负责企业级客户。",
        "工作经历", "2020-至今 星链数据 销售总监", "管理 15 人团队，年度销售额 9800 万元。",
        "熟悉团队管理、大客户与英语商务沟通。",
    ],
    "汤文渊_制造业区域经理.docx": [
        "汤文渊", "广州 | 13800000016 | tang.demo@example.com", "现任职位：区域经理",
        "10 年制造业设备销售经验，覆盖华南区域。",
        "工作经历", "2019-至今 粤工装备 区域经理", "管理 12 人团队，负责渠道管理，年度业绩 7200 万元。",
        "熟悉渠道管理、项目管理与 CRM。",
    ],
    "白晓宁_销售工程师.docx": [
        "白晓宁", "广州 | 13800000008 | bai.demo@example.com", "现任职位：销售工程师",
        "4 年制造业设备销售经验，支持华南区域客户。",
        "工作经历", "2024-至今 南粤精工 销售工程师", "协助完成年度业绩 1200 万元。",
        "熟悉 CRM 与项目管理。",
    ],
    # ---------- 非销售方向（用于验证"不应被召回"的负样本） ----------
    "邱文彬_财务总监.docx": [
        "邱文彬", "上海 | 13800000004 | qiu.demo@example.com", "现任职位：CFO",
        "16 年财务管理经验，负责集团财务与投融资。", "工作经历", "2015-至今 华芯设备 财务总监",
        "管理 20 人财务团队，完成两轮融资，年度预算规模 8 亿元。", "熟悉项目管理与英语商务沟通。",
    ],
    "邓嘉睿_财务总监.docx": [
        "邓嘉睿", "杭州 | 13800000013 | deng.demo@example.com", "现任职位：财务总监",
        "15 年制造业财务管理经验。", "工作经历", "2016-至今 绿能科技 财务总监",
        "管理 12 人财务团队，负责年度预算与成本管控，年度成本下降 9%。", "熟悉项目管理与 CRM 系统实施。",
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="写入虚构演示简历")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先删除本脚本生成的演示文档再重新导入（不会动你自己上传的简历）",
    )
    args = parser.parse_args()

    bootstrap()
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    if args.reset:
        with SessionLocal() as db:
            stale = list(db.scalars(select(ResumeDocument).where(ResumeDocument.filename.in_(list(SAMPLES)))))
            for document in stale:
                # Cascade removes the candidate, experiences, chunks and task.
                db.delete(document)
            db.commit()
        for filename in SAMPLES:
            path = settings.upload_dir / filename
            if path.exists():
                path.unlink()
        print(f"--reset：已清除 {len(stale)} 份旧演示文档")

    created = skipped = 0
    for filename, paragraphs in SAMPLES.items():
        # Keep the demo command idempotent even though DOCX metadata changes
        # on each save (and would otherwise produce a new SHA-256 every run).
        with SessionLocal() as db:
            if db.scalar(select(ResumeDocument).where(ResumeDocument.filename == filename)):
                skipped += 1
                continue
        path = settings.upload_dir / filename
        docx = Document()
        for line in paragraphs:
            docx.add_paragraph(line)
        docx.save(path)
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        with SessionLocal() as db:
            if db.scalar(select(ResumeDocument).where(ResumeDocument.sha256 == digest)):
                skipped += 1
                continue
            row = ResumeDocument(filename=filename, content_type=DOCX_MIME, sha256=digest, storage_path=str(path))
            db.add(row)
            db.flush()
            task = ImportTask(document_id=row.id)
            db.add(task)
            db.commit()
            process_document(row.id, task.id)
            created += 1
    print(f"演示简历就绪：新增 {created} 份，已存在跳过 {skipped} 份，共 {len(SAMPLES)} 份。")


if __name__ == "__main__":
    main()
