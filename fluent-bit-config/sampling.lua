function subsample_info(tag, timestamp, record)
    local log_message = record["log"] or record["message"] or ""
    local log_lower = string.lower(log_message)

    -- Always keep ERROR, FATAL, WARN, PANIC logs
    if string.match(log_lower, "error") or
       string.match(log_lower, "fatal") or
       string.match(log_lower, "warn") or
       string.match(log_lower, "panic") then
        return 1, timestamp, record
    end

    -- For INFO/DEBUG logs, sample at 50%
    if string.match(log_lower, "info") or
       string.match(log_lower, "debug") then
        -- Sample 50% (keep 1 out of 2)
        if math.random(2) == 1 then
            return 1, timestamp, record
        else
            return -1, timestamp, record  -- Drop the record
        end
    end

    -- Keep logs without level indicators at 50% as well
    if math.random(2) == 1 then
        return 1, timestamp, record
    else
        return -1, timestamp, record
    end
end