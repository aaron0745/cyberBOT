const mongoose = require('mongoose');

// Schemas based on the original Python SQLite setup
const FlagSchema = new mongoose.Schema({
    challenge_id: { type: String, required: true, unique: true },
    flag_text: { type: String, required: true },
    points: { type: Number, default: 0 },
    category: { type: String, default: 'General' },
    msg_id: { type: String },
    file_msg_id: { type: String },
    channel_id: { type: String },
    image_url: { type: String },
    posted_at: { type: Number },
    start_time: { type: Number },
    end_time: { type: Number }, // Unix timestamp for manual interval checks
    description: { type: String },
    connection_info: { type: String },
    file_url: { type: String } // Replaces local file_path for Discord attachments
});

const RoleRewardSchema = new mongoose.Schema({
    role_id: { type: String, required: true, unique: true },
    points: { type: Number, required: true }
});

const ScoreSchema = new mongoose.Schema({
    user_id: { type: String, required: true, unique: true },
    username: { type: String },
    points: { type: Number, default: 0 }
});

const SolveSchema = new mongoose.Schema({
    user_id: { type: String, required: true },
    challenge_id: { type: String, required: true },
    timestamp: { type: Number, required: true },
    points_awarded: { type: Number } // Add points_awarded
});
SolveSchema.index({ user_id: 1, challenge_id: 1 }, { unique: true });

const BanlistSchema = new mongoose.Schema({
    user_id: { type: String, required: true, unique: true }
});

const HintSchema = new mongoose.Schema({
    challenge_id: { type: String, required: true },
    hint_text: { type: String, required: true },
    cost: { type: Number, default: 0 }
});

const ConfigSchema = new mongoose.Schema({
    key: { type: String, required: true, unique: true },
    value: { type: mongoose.Schema.Types.Mixed }
});

const UnlockedHintSchema = new mongoose.Schema({
    user_id: { type: String, required: true },
    hint_id: { type: String, required: true }
});
UnlockedHintSchema.index({ user_id: 1, hint_id: 1 }, { unique: true });

const Models = {
    Flag: mongoose.model('Flag', FlagSchema),
    RoleReward: mongoose.model('RoleReward', RoleRewardSchema),
    Score: mongoose.model('Score', ScoreSchema),
    Solve: mongoose.model('Solve', SolveSchema),
    Banlist: mongoose.model('Banlist', BanlistSchema),
    Hint: mongoose.model('Hint', HintSchema),
    Config: mongoose.model('Config', ConfigSchema),
    UnlockedHint: mongoose.model('UnlockedHint', UnlockedHintSchema)
};

async function connectDB() {
    try {
        mongoose.connection.on('disconnected', () => {
            console.log('⚠️ MongoDB disconnected! Attempting to reconnect...');
        });
        
        mongoose.connection.on('reconnected', () => {
            console.log('✅ MongoDB reconnected successfully!');
        });
        
        mongoose.connection.on('error', (err) => {
            console.error('❌ MongoDB Connection Error:', err);
        });

        await mongoose.connect(process.env.MONGODB_URI, {
            serverSelectionTimeoutMS: 5000,
        });
        console.log('✅ Connected to MongoDB Atlas');
    } catch (error) {
        console.error('❌ Initial MongoDB Connection Error:', error);
    }
}

module.exports = { connectDB, Models };
