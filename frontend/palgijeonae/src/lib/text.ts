// .length/.slice()는 코드 유닛 단위라 이모지를 반으로 자르므로, grapheme(글자) 단위로 다룬다.
const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

export function countGraphemes(text: string): number {
    return Array.from(segmenter.segment(text)).length;
}

export function truncateGraphemes(text: string, maxLength: number): string {
    const graphemes = Array.from(segmenter.segment(text), (s) => s.segment);
    return graphemes.length > maxLength ? graphemes.slice(0, maxLength).join("") : text;
}

// 백엔드 길이 제한(.length, 자바 String.length()와 동일한 UTF-16 코드 유닛 기준)에 맞춰 자르되,
// 이모지가 코드 유닛 중간에서 잘리지 않도록 grapheme 단위로 묶어서 채운다.
export function truncateToCodeUnitLength(text: string, maxLength: number): string {
    if (text.length <= maxLength) {
        return text;
    }
    let result = "";
    for (const { segment } of segmenter.segment(text)) {
        if (result.length + segment.length > maxLength) {
            break;
        }
        result += segment;
    }
    return result;
}
