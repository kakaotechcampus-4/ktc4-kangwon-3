import { type ClassValue,clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// clsx로 조건부 클래스를 조합하고, tailwind-merge로 충돌하는 Tailwind 클래스를 정리한다.
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
