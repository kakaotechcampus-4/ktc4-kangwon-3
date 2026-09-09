import React from "react";


interface DefaultBoxProps {
  width?: string; 
  align?: "left" | "right";
  variant?: "solid" | "dashed"; 
  className?: string;
  children: React.ReactNode;
}


const BASE_CLASSES =
  "flex flex-col h-auto box-border py-[18px] px-6 rounded-[10px] border-[#9d9d9d] gap-5";

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
