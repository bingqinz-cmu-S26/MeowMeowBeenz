import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { FilterChips } from '@/components/ui/FilterChips';
import { Panel } from '@/components/ui/Panel';
import { Screen } from '@/components/ui/Screen';
import { ScreenHeader } from '@/components/ui/ScreenHeader';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';

const prompts = [
  { id: 'today', label: 'How are the cats today?' },
  { id: 'attention', label: 'Which cat needs attention?' },
  { id: 'worry', label: 'Should I worry?' },
];

export default function AgentScreen() {
  const { chat, sendMessage } = useApp();
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const question = input.trim();
    if (!question) return;
    setInput('');
    await sendMessage(question);
  };

  return (
    <Screen
      footer={
        <View style={styles.footer}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Ask Beenz"
            placeholderTextColor={Theme.muted}
            style={styles.input}
            onSubmitEditing={handleSend}
          />
          <Pressable onPress={handleSend} style={styles.send}>
            <Text style={styles.sendText}>Send</Text>
          </Pressable>
        </View>
      }>
      <ScreenHeader
        eyebrow="Cat wellness assistant"
        title="Agent"
        subtitle="Ask about routines, vocalizations, activity, and whether a pattern is worth watching."
      />

      <Panel eyebrow="Quick prompts" title="Start here">
        <FilterChips
          options={prompts}
          value="today"
          onChange={(id) => {
            const prompt = prompts.find((item) => item.id === id);
            if (prompt) sendMessage(prompt.label);
          }}
        />
      </Panel>

      <Panel eyebrow="Chat" title="Beenz">
        <View style={styles.chat}>
          {chat.map((message, index) => (
            <View
              key={`${message.role}-${index}`}
              style={[styles.bubble, message.role === 'owner' ? styles.owner : styles.assistant]}>
              <Text style={styles.bubbleText}>{message.text}</Text>
              {message.provider ? <Text style={styles.provider}>{message.provider}</Text> : null}
            </View>
          ))}
        </View>
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  chat: { gap: 10 },
  bubble: {
    borderRadius: 12,
    padding: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: Theme.line,
  },
  owner: { backgroundColor: Theme.panel2, alignSelf: 'flex-end', maxWidth: '90%' },
  assistant: { backgroundColor: '#1d2420', alignSelf: 'flex-start', maxWidth: '95%' },
  bubbleText: { color: Theme.text, fontSize: 14, lineHeight: 20 },
  provider: { color: Theme.muted, fontSize: 11, textTransform: 'uppercase' },
  footer: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: Theme.text,
    backgroundColor: Theme.panel2,
  },
  send: {
    backgroundColor: Theme.button,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  sendText: { color: Theme.buttonText, fontWeight: '700' },
});
