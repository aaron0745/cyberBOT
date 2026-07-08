const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('create')
        .setDescription('Add a new challenge to the database')
        .addStringOption(option => 
            option.setName('challenge_id')
                .setDescription('Unique ID for the challenge (e.g. web1)')
                .setRequired(true)
        )
        .addStringOption(option => 
            option.setName('flag_text')
                .setDescription('The answer flag (e.g., flag{h4ck3d})')
                .setRequired(true)
        )
        .addIntegerOption(option => 
            option.setName('points')
                .setDescription('Base points awarded for solving')
                .setRequired(true)
                .setMinValue(0)
        )
        .addStringOption(option => 
            option.setName('category')
                .setDescription('Choose from the official specialization list')
                .setRequired(true)
                .addChoices(
                    { name: "🌐 WEB", value: "WEB" },
                    { name: "🔐 CRYPTO", value: "CRYPTO" },
                    { name: "💥 PWN", value: "PWN" },
                    { name: "⚙️ REV", value: "REV" },
                    { name: "🔍 FORENSICS", value: "FORENSICS" },
                    { name: "👁️ OSINT", value: "OSINT" },
                    { name: "🧩 MISC", value: "MISC" }
                )
        )
        .addStringOption(option => 
            option.setName('image_url')
                .setDescription('Optional image link')
                .setRequired(false)
        )
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        const challenge_id = interaction.options.getString('challenge_id');
        const flag_text = interaction.options.getString('flag_text');
        const points = interaction.options.getInteger('points');
        const category = interaction.options.getString('category');
        const image_url = interaction.options.getString('image_url');

        if (!/^[a-zA-Z0-9_-]+$/.test(challenge_id)) {
            return interaction.editReply({ content: '❌ Challenge ID can only contain letters, numbers, underscores, and dashes.' });
        }

        try {
            const existing = await Models.Flag.findOne({ challenge_id });
            if (existing) {
                return interaction.editReply({ content: `❌ A challenge with ID \`${challenge_id}\` already exists!` });
            }

            await Models.Flag.create({
                challenge_id,
                flag_text,
                points,
                category,
                image_url
            });

            await interaction.editReply({ 
                content: `✅ Successfully created challenge **${challenge_id}**!\nNext step: use \`/post\` to publish it.` 
            });
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ An error occurred while creating the challenge.' });
        }
    },
};
