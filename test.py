import time

from lru_cache_package import lru_cache, LRUCacheDict


# Test case 1
@lru_cache(max_size=1024, expire_time=3)
def f(x):
    print(" Create f(" + str(x) + ")")
    return x


f(3)
time.sleep(2)

print("output: ", f(3))

# Test case 2
d = LRUCacheDict(max_size=3, expire_time=3)
d['1'] = '2'
print(d['1'])
time.sleep(4)  # 4 seconds > 3 second cache expiry of d
print(d['1'])  # KeyError
