local client_list = redis.call('client', 'list')
local locks = redis.call('keys', 'lock:*:[RW]:*')
for i, lock in ipairs(locks) do
    local owner = string.match(lock, 'lock:.+:[RW]:(.*)')
    if string.find(client_list, 'name='..owner, 1, true) == nil then
        local name = string.match(lock, 'lock:(.+):[RW]:.+')
        local mode = string.match(lock, 'lock:.+:([RW]):.+')
        redis.call('del', lock)
        redis.call('srem', 'rsrc:'..name, mode..':'..onwer)
        if redis.call('scard', 'rsrc:'..name) == 0 then
            redis.call('del', 'rsrc:'..name)
        end
    end
end
