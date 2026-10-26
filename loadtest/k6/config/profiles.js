// 부하 프로파일. 동시 세션 수(CONCURRENT)를 리틀의 법칙으로 도착률(분당 세션)로 바꿔 open model로 넣는다.
//   도착률 = 동시 세션 ÷ 세션 길이. 세션 길이(SESSION_SECONDS)는 AI 처리 1~2분 + 폴링·생각 시간 ≈ 150초
// closed model(VU 고정)은 서버가 느려지면 요청률도 같이 줄어 병목이 가려지므로 쓰지 않는다.
const SESSION_SECONDS = Number(__ENV.SESSION_SECONDS || 150);

export function sessionsPerMinute(concurrent) {
  if (concurrent <= 0) {
    return 0;
  }
  return Math.max(1, Math.round((concurrent * 60) / SESSION_SECONDS));
}

// 도착률을 감당할 VU 수 = 도착률 × 세션 길이. 서버가 느려지면 세션이 길어지므로 maxVUs는 넉넉히
function vus(peakConcurrent) {
  return { preAllocatedVUs: Math.ceil(peakConcurrent * 1.2), maxVUs: Math.ceil(peakConcurrent * 3) };
}

const stage = (minutes, concurrent) => ({ duration: `${minutes}m`, target: sessionsPerMinute(concurrent) });

// 진단 세션 시나리오. 둘러보기 세션은 진단 세션의 BROWSE_RATIO배로 함께 넣는다.
export function journeyScenarios(profile, concurrent) {
  const builders = {
    // 목표 동시 세션으로 올린 뒤 유지
    load: () => ({ stages: [stage(2, concurrent), stage(10, concurrent), stage(1, 0)], peak: concurrent }),
    // 50 → 100 → 200 → 400처럼 두 배씩 올리며 SLO가 깨지는 지점을 찾는다. 단계마다 정상 상태(세션 길이 이상) 유지
    stress: () => {
      const steps = (__ENV.STRESS_STEPS || '50,100,200,400').split(',').map(Number);
      return {
        stages: steps.flatMap((c) => [stage(1, c), stage(5, c)]).concat([stage(1, 0)]),
        peak: steps[steps.length - 1],
      };
    },
    // 평소 부하에서 갑자기 몰렸다가 돌아온 뒤 회복하는지
    spike: () => {
      const base = Math.max(1, Math.round(concurrent / 5));
      const peak = Number(__ENV.SPIKE_PEAK || concurrent * 4);
      return {
        stages: [stage(3, base), { duration: '30s', target: sessionsPerMinute(peak) }, stage(2, peak),
          { duration: '30s', target: sessionsPerMinute(base) }, stage(5, base), stage(1, 0)],
        peak,
      };
    },
    // 오래 돌려 누수(메모리·커넥션)와 큐 증가를 본다
    soak: () => {
      const level = Math.round(concurrent * 0.7);
      return { stages: [stage(2, level), stage(Number(__ENV.SOAK_MINUTES || 45), level), stage(1, 0)], peak: level };
    },
  };
  const build = builders[profile];
  if (!build) {
    throw new Error(`알 수 없는 PROFILE: ${profile} (load | stress | spike | soak)`);
  }
  const { stages, peak } = build();
  const browseRatio = Number(__ENV.BROWSE_RATIO || 1);

  const scenarios = {
    diagnosis: {
      executor: 'ramping-arrival-rate',
      exec: 'diagnosis',
      startRate: 0,
      timeUnit: '1m',
      stages,
      // 마지막 단계가 끝나도 진행 중인 진단(최대 수 분)을 끝까지 따라가게
      gracefulStop: '5m',
      ...vus(peak),
    },
  };
  if (browseRatio > 0) {
    scenarios.browse = {
      executor: 'ramping-arrival-rate',
      exec: 'browse',
      startRate: 0,
      timeUnit: '1m',
      stages: stages.map((s) => ({ ...s, target: Math.round(s.target * browseRatio) })),
      gracefulStop: '30s',
      // 둘러보기 세션은 약 10초라 VU가 적게 든다
      preAllocatedVUs: 10,
      maxVUs: Math.max(20, Math.ceil(peak * 0.5)),
    };
  }
  return scenarios;
}

// 단일 API 기준선: 초당 요청 수를 단계별로 올린다(STEPS="10,25,50,100", STEP_MINUTES=2).
export function rpsSteps(defaultSteps) {
  const steps = (__ENV.STEPS || defaultSteps).split(',').map(Number);
  const minutes = Number(__ENV.STEP_MINUTES || 2);
  return {
    executor: 'ramping-arrival-rate',
    startRate: 0,
    timeUnit: '1s',
    stages: steps.flatMap((rps) => [{ duration: '30s', target: rps }, { duration: `${minutes}m`, target: rps }])
      .concat([{ duration: '30s', target: 0 }]),
    preAllocatedVUs: 20,
    maxVUs: Number(__ENV.MAX_VUS || 300),
  };
}
