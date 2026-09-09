import kakao from "../../assets/login-kakao.png"
import naver from "../../assets/login-naver.png"
import google from "../../assets/login-google.png"

import LoginButton from "./LoginButton.tsx"

function LoginPage() {
    return (
        <div>
            <LoginButton
                type="카카오"
                image={kakao}
                BorderColor="gray-300"
                BackgroundColor="yellow-400"
                textColor="black"
                onClick={() => {
                    // 카카오 로그인 로직
                }}
            />
            <LoginButton
                type="네이버"
                image={naver}
                BorderColor="green-500"
                BackgroundColor="green-500"
                textColor="white"
                onClick={() => {
                    // 네이버 로그인 로직
                }}
            />
            <LoginButton
                type="구글"
                image={google}
                BorderColor="gray-300"
                BackgroundColor="white"
                textColor="black"
                onClick={() => {
                    // 구글 로그인 로직
                }}
            />
        </div>
    );
}

export default LoginPage;