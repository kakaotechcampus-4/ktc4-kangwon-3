import React from "react";

/**
 * InputBox
 * Figma "업로드 화면" 상품 정보 입력 박스를 컴포넌트화한 레이아웃 wrapper.
 *
 * - height: 항상 auto (내용물에 맞춰 늘어남)
 * - width: 기본 full, props로 커스텀 값 전달 가능 (e.g. "480px", "60%", "w-[360px]" 등 tailwind 클래스도 가능)
 * - align: 내부 콘텐츠 정렬, "left"(기본) | "right"
 * - padding / border / radius는 디자인 토큰으로 고정 (내부 상수, props로 안 받음)
 * - children으로 내용은 자유롭게 구성 (인풋, 드롭존, 리스트 등 무엇이든)
 */

interface DefaultBoxProps {
  width?: string; // "full" | 임의의 tailwind width 값 or CSS 값 (e.g. "360px", "w-1/2")
  align?: "left" | "right";
  variant?: "solid" | "dashed"; // 드롭존처럼 점선 테두리가 필요한 경우
  className?: string;
  children: React.ReactNode;
}

// 고정 디자인 토큰 (props로 노출하지 않음)
const BASE_CLASSES =
  "flex flex-col h-auto box-border py-[18px] px-6 rounded-[10px] border-[#9d9d9d]";

function DefaultBox({
  width = "full",
  align = "left",
  variant = "solid",
  className = "",
  children,
}: DefaultBoxProps) {
  const widthClass = width === "full" ? "w-full" : width;
  const alignClass =
    align === "right" ? "items-end text-right" : "items-start text-left";
  const borderClass = variant === "dashed" ? "border border-dashed" : "border border-solid";

  return (
    <div
      className={`${BASE_CLASSES} ${widthClass} ${alignClass} ${borderClass} ${className}`}
    >
      {children}
    </div>
  );
}

export default DefaultBox;
