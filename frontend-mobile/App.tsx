import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import React from "react";
import { TouchableOpacity, Text } from "react-native";
import AgentDashboardScreen from "./src/screens/AgentDashboardScreen";
import CustomerChatScreen from "./src/screens/CustomerChatScreen";

export type RootStackParamList = {
  CustomerChat: undefined;
  AgentDashboard: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const SPOTIFY_GREEN = "#1db954";
const SPOTIFY_DARK = "#181818";
const SPOTIFY_BLACK = "#121212";

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator
        initialRouteName="CustomerChat"
        screenOptions={{
          headerStyle: { backgroundColor: SPOTIFY_DARK },
          headerTintColor: "#ffffff",
          headerTitleStyle: { fontWeight: "600", fontSize: 15 },
          contentStyle: { backgroundColor: SPOTIFY_BLACK },
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen
          name="CustomerChat"
          component={CustomerChatScreen}
          options={({ navigation }) => ({
            headerShown: false, // header is built into the screen itself
          })}
        />
        <Stack.Screen
          name="AgentDashboard"
          component={AgentDashboardScreen}
          options={{ headerShown: false }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
