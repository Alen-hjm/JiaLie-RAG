import { StarFilled, StarOutlined } from "@ant-design/icons";
import { Button, message } from "antd";
import { toggleShortlist, useShortlist } from "../shortlist";

export function SaveCandidate({
  id,
  compact = false,
}: {
  id: string;
  compact?: boolean;
}) {
  const saved = useShortlist().includes(id);
  return (
    <Button
      className={`save-candidate ${saved ? "saved" : ""}`}
      aria-label={saved ? "取消收藏" : "收藏候选人"}
      aria-pressed={saved}
      type="text"
      icon={saved ? <StarFilled /> : <StarOutlined />}
      onClick={(event) => {
        event.stopPropagation();
        try {
          toggleShortlist(id);
          message.success(
            saved ? "已取消收藏" : "已加入我的收藏，可在收藏页对比人才",
          );
        } catch {
          message.error("浏览器暂时无法保存，请检查本地存储设置后重试。");
        }
      }}
    >
      {!compact && (saved ? "已收藏" : "收藏")}
    </Button>
  );
}
