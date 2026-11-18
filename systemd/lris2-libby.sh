# Export LIBBY_RABBITMQ_URL from /etc/lris2/secrets.env for lris2-ops members
if [ -r /etc/lris2/secrets.env ]; then
    LIBBY_RABBITMQ_URL=$(sed -n 's/^LIBBY_RABBITMQ_URL=//p' /etc/lris2/secrets.env)
    [ -n "$LIBBY_RABBITMQ_URL" ] && export LIBBY_RABBITMQ_URL || unset LIBBY_RABBITMQ_URL
fi
