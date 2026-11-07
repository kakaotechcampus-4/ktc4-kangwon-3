import { useNavigate } from "react-router-dom";

import { SourceType } from "@/api/types";
import demoFan from "@/assets/main-demoFan.png";
import demoHamburgerToy from "@/assets/main-demoHamburgerToy.png";
import demoKatana from "@/assets/main-demoKatana.png";
import type { Product } from "@/pages/Upload/types";

interface DemoProductSeed {
    title: string
    link: string
    thumbnail: string
}

// AI 테스트에 실제로 썼던 상품 중, 서로 다른 규제 분야를 보여주도록 3개 선정.
const DEMO_PRODUCT_SEEDS: DemoProductSeed[] = [
    {
        title: "인기 있는 역할 놀이 나무 햄버거 샌드위치 장난감 어린이용",
        link: "https://kr.made-in-china.com/co_ningboshone/product_Popular-Role-Play-Wooden-Hamburger-Sandwich-Toys-for-Kids_ysnoyheroy.html",
        thumbnail: demoHamburgerToy,
    },
    {
        title: "104cm 카마도 탄지로 카타나 탄소강 악마 사냥꾼 검",
        link: "https://kr.made-in-china.com/co_zhengssword/product_104cm-Kamado-Tanjirou-Katana-Carbon-Steel-Demon-Slayer-Sword_ysuusoosig.html",
        thumbnail: demoKatana,
    },
    {
        title: "16 18 스탠드 팬 ABS 바디 고품질 전기 팬 타이머 포함",
        link: "https://kr.made-in-china.com/co_goldenfeng/product_16-18-Stand-Fan-ABS-Body-High-Quality-Electric-Fan-with-Timer_uoeseyeeey.html",
        thumbnail: demoFan,
    },
];

// 번들된 썸네일 에셋을 fetch해서 File로 바꾼다. 
async function assetToFile(assetUrl: string, fileName: string): Promise<File> {
    const response = await fetch(assetUrl);
    const blob = await response.blob();
    return new File([blob], fileName, { type: blob.type });
}

/** 예시 상품 3개를 썸네일까지 이미 담긴 상태로 업로드 페이지로 이동시킨다. */
export function useDemoStart() {
    const navigate = useNavigate();

    return async () => {
        const demoProducts: Product[] = await Promise.all(
            DEMO_PRODUCT_SEEDS.map(async ({ title, link, thumbnail }, index) => ({
                id: crypto.randomUUID(),
                type: SourceType.Url,
                title,
                link,
                productImageFile: await assetToFile(thumbnail, `demo-thumbnail-${index}.png`),
            })),
        );
        navigate("/upload", { state: { demoProducts } });
    };
}
