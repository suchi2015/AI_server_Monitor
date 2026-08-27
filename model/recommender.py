"""
Recommendation Engine:
- Maps root cause patterns to concrete fix steps
- Returns ordered list of actionable recommendations
"""
from typing import List


# ── Recommendation knowledge base ─────────────────────────────────────────────
# Each entry: (keyword_in_root_cause, list_of_steps)

RECOMMENDATIONS = [

    ("Memory exhaustion", [
        "1. Immediately check memory usage: `free -h` or `top` on the server",
        "2. Identify the top memory-consuming process: `ps aux --sort=-%mem | head -10`",
        "3. Restart the affected service if safe: `systemctl restart <service>`",
        "4. Check for memory leaks in application code (heap dumps, profiling)",
        "5. If recurring: upgrade EC2 instance type (t2.micro → t2.small has 2GB RAM)",
        "6. Add swap space as a buffer: `sudo fallocate -l 2G /swapfile`",
    ]),

    ("connection pool exhausted", [
        "1. Check current DB connections: `SELECT count(*) FROM pg_stat_activity;` (Postgres)",
        "2. Kill idle connections: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle';`",
        "3. Reduce connection pool size in app config (e.g., Mongoose: `poolSize: 5`)",
        "4. Add connection timeout settings to prevent connection leaks",
        "5. Consider using PgBouncer (connection pooler) in front of Postgres",
        "6. Set `max_connections` in postgresql.conf appropriately for t2.micro",
    ]),

    ("Disk space exhaustion", [
        "1. Check disk usage: `df -h` and `du -sh /* | sort -rh | head -20`",
        "2. Find large log files: `find /var/log -size +100M`",
        "3. Clear old logs: `journalctl --vacuum-time=3d` or `logrotate -f /etc/logrotate.conf`",
        "4. If Postgres WAL: `SELECT pg_size_pretty(pg_database_size('mydb'));`",
        "5. Set up automatic log rotation in your application",
        "6. Expand EBS volume in AWS console (EC2 → Volumes → Modify)",
    ]),

    ("Cache layer failure", [
        "1. Check Redis status: `redis-cli ping` (should return PONG)",
        "2. Check Redis memory: `redis-cli info memory | grep used_memory_human`",
        "3. If OOM: set eviction policy: `redis-cli config set maxmemory-policy allkeys-lru`",
        "4. Flush expired keys: `redis-cli FLUSHDB` (WARNING: clears all cache)",
        "5. Restart Redis: `systemctl restart redis`",
        "6. Check Redis config: `maxmemory` should be set to ~80% of available RAM",
    ]),

    ("High CPU utilization", [
        "1. Identify CPU-heavy process: `top -b -n1 | head -20` or `htop`",
        "2. Check for runaway processes: `ps aux --sort=-%cpu | head -10`",
        "3. If Node.js: check event loop lag, add `--max-old-space-size` flag",
        "4. Check for cron jobs running at wrong time",
        "5. Enable CloudWatch detailed monitoring to track CPU trend",
        "6. If sustained: scale up to t2.small or add auto-scaling",
    ]),

    ("High RAM utilization", [
        "1. Check RAM usage: `free -h` and identify top consumers with `ps aux --sort=-%mem`",
        "2. Check for memory leaks: monitor process RSS over time",
        "3. Restart leaking service to free memory (temporary fix)",
        "4. Add swap: `sudo fallocate -l 1G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`",
        "5. Profile your Node.js app with `node --inspect` and Chrome DevTools",
        "6. Upgrade instance type if workload genuinely requires more RAM",
    ]),

    ("Database performance", [
        "1. Check slow query log: enable in MySQL/Postgres config",
        "2. Run EXPLAIN ANALYZE on slow queries to find missing indexes",
        "3. Add indexes on frequently queried fields",
        "4. Check for N+1 query problems in your ORM (Mongoose populate, Sequelize include)",
        "5. Enable query caching where appropriate",
        "6. Consider read replicas if read-heavy workload",
    ]),

    ("Network/upstream failure", [
        "1. Check if upstream service is running: `curl -v http://localhost:<port>/health`",
        "2. Check firewall/security groups in AWS console (EC2 → Security Groups)",
        "3. Verify DNS resolution: `nslookup <hostname>`",
        "4. Check nginx/proxy config: `nginx -t && systemctl status nginx`",
        "5. Review AWS VPC routing tables if inter-service communication",
        "6. Add retry logic with exponential backoff in your application",
    ]),

    ("Authentication/authorization failure", [
        "1. Check if API keys/tokens have expired",
        "2. Verify IAM roles and policies in AWS console",
        "3. Check application environment variables for correct credentials",
        "4. Review recent security group or IAM policy changes",
        "5. Check application logs for specific auth error messages",
        "6. Rotate credentials if compromise is suspected",
    ]),

    ("Service cascade failure", [
        "1. Identify the root dependency that failed first (check timestamps in incident timeline)",
        "2. Restore the shared dependency first (DB, Redis, or network)",
        "3. Restart services in dependency order (DB first, then cache, then app)",
        "4. Add circuit breaker pattern to prevent cascade in future",
        "5. Implement health checks and graceful degradation in each service",
        "6. Set up CloudWatch composite alarms for cascade detection",
    ]),

    ("Repeated error burst", [
        "1. Temporarily stop the retry loop: disable the failing job/worker",
        "2. Check what the service is retrying against (is the dependency down?)",
        "3. Fix the underlying issue before re-enabling retries",
        "4. Add exponential backoff to retry logic (not immediate retry)",
        "5. Add a circuit breaker to stop retrying after N failures",
        "6. Set max retry count to prevent infinite loops",
    ]),
]

GENERIC = [
    "1. Review the incident timeline and correlated events in the dashboard",
    "2. Check application logs for the affected service",
    "3. Verify all dependent services are running: `systemctl status <service>`",
    "4. Check system resources: `top`, `free -h`, `df -h`",
    "5. Review recent deployments or config changes that may have caused this",
    "6. Check AWS CloudWatch metrics for the EC2 instance",
]


def get_recommendations(root_cause: str) -> List[str]:
    """
    Returns list of fix steps based on root cause string.
    """
    if not root_cause:
        return GENERIC
    rc_lower = root_cause.lower()
    for keyword, steps in RECOMMENDATIONS:
        if keyword.lower() in rc_lower:
            return steps
    return GENERIC
