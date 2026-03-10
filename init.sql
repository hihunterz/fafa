CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    username TEXT,
    name TEXT,
    rating FLOAT DEFAULT 0,
    reviews_count INT DEFAULT 0
);

CREATE TABLE ads (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    type TEXT,
    category TEXT,
    title TEXT,
    description TEXT,
    price TEXT,
    channel_message_id TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE responses (
    id SERIAL PRIMARY KEY,
    ad_id INT REFERENCES ads(id),
    responder_user_id INT REFERENCES users(id),
    message TEXT,
    offered_price TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    from_user_id INT REFERENCES users(id),
    to_user_id INT REFERENCES users(id),
    rating INT,
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);