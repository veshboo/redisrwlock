-- redis-cli --ldb --eval scratch.lua , 1482412261.182691
--- local time = redis.call('time') -- non-deterministic
local retval = redis.call('get', 'lock-name-x')
if retval == false then
    local refcnt = '1'
    local time = ARGV[1]
    redis.call('set', 'lock-name-x', refcnt..':'..time)
else
    local refcnt = tonumber(string.match(retval, '(.+):.+')) + 1
    local time = string.match(retval, '.+:(.+)')
    redis.call('set', 'lock-name-x', refcnt..':'..time)
end
print('DEBUG lock-name-x='..redis.call('get', 'lock-name-x'))
