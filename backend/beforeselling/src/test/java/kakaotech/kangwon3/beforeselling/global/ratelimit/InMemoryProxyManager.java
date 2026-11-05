package kakaotech.kangwon3.beforeselling.global.ratelimit;

import io.github.bucket4j.distributed.proxy.ClientSideConfig;
import io.github.bucket4j.distributed.proxy.generic.compare_and_swap.AbstractCompareAndSwapBasedProxyManager;
import io.github.bucket4j.distributed.proxy.generic.compare_and_swap.AsyncCompareAndSwapOperation;
import io.github.bucket4j.distributed.proxy.generic.compare_and_swap.CompareAndSwapOperation;
import io.github.bucket4j.distributed.remote.RemoteBucketState;

import java.util.Arrays;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Redis 없이 Bucket4j 계산을 그대로 검증하기 위한 메모리 저장소 ProxyManager.
 */
class InMemoryProxyManager extends AbstractCompareAndSwapBasedProxyManager<String> {

    private final Map<String, byte[]> store = new ConcurrentHashMap<>();

    InMemoryProxyManager() {
        super(ClientSideConfig.getDefault());
    }

    @Override
    protected CompareAndSwapOperation beginCompareAndSwapOperation(String key) {
        return new CompareAndSwapOperation() {
            @Override
            public Optional<byte[]> getStateData(Optional<Long> timeoutNanos) {
                return Optional.ofNullable(store.get(key));
            }

            @Override
            public boolean compareAndSwap(byte[] originalData, byte[] newData, RemoteBucketState newState,
                                          Optional<Long> timeoutNanos) {
                boolean[] swapped = {false};
                store.compute(key, (k, current) -> {
                    if (Arrays.equals(current, originalData)) {
                        swapped[0] = true;
                        return newData;
                    }
                    return current;
                });
                return swapped[0];
            }
        };
    }

    @Override
    protected AsyncCompareAndSwapOperation beginAsyncCompareAndSwapOperation(String key) {
        throw new UnsupportedOperationException();
    }

    @Override
    public void removeProxy(String key) {
        store.remove(key);
    }

    @Override
    protected CompletableFuture<Void> removeAsync(String key) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean isAsyncModeSupported() {
        return false;
    }
}
