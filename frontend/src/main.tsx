import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "./design.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#7560aa",
          colorText: "#29272d",
          colorTextSecondary: "#77727c",
          colorBorder: "#e8e3dd",
          borderRadius: 10,
          controlHeight: 38,
          fontFamily:
            'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif',
        },
        components: {
          Button: { primaryShadow: "none" },
          Input: { activeShadow: "0 0 0 3px rgba(117, 96, 170, .10)" },
          Modal: { borderRadiusLG: 18 },
          Drawer: { colorBgElevated: "#ffffff" },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);
