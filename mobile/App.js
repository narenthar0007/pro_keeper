import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { api, getToken, setToken } from './src/api';
import {
  AdminScreen,
  BuildingsScreen,
  DashboardScreen,
  InboxScreen,
  LeadsScreen,
  ListingDetailScreen,
  ListingsScreen,
  LoginScreen,
  MoreScreen,
  PortalScreen,
  PropertiesScreen,
  PropertyDetailScreen,
  PropertyFormScreen,
  ReminderScreen,
  TenantFormScreen,
  TenantsScreen,
} from './src/screens';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function hasPriv(user, code) {
  if (!user) return false;
  if (user.is_admin) return true;
  return (user.privileges || []).includes(code);
}

function BrowseStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Listings" component={ListingsScreen} options={{ title: 'Browse' }} />
      <Stack.Screen name="ListingDetail" component={ListingDetailScreen} options={{ title: 'Listing' }} />
    </Stack.Navigator>
  );
}

function PropertyStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="PropertyList" component={PropertiesScreen} options={{ title: 'Properties' }} />
      <Stack.Screen name="PropertyDetail" component={PropertyDetailScreen} options={{ title: 'Manage' }} />
      <Stack.Screen name="PropertyForm" component={PropertyFormScreen} options={{ title: 'Property' }} />
      <Stack.Screen name="TenantForm" component={TenantFormScreen} options={{ title: 'Tenant' }} />
    </Stack.Navigator>
  );
}

function TenantStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="TenantList" component={TenantsScreen} options={{ title: 'Tenants' }} />
      <Stack.Screen name="TenantForm" component={TenantFormScreen} options={{ title: 'Tenant' }} />
    </Stack.Navigator>
  );
}

function MoreStack({ user, onLogout }) {
  return (
    <Stack.Navigator>
      <Stack.Screen name="MoreHome" options={{ title: 'More' }}>
        {(props) => <MoreScreen {...props} user={user} onLogout={onLogout} />}
      </Stack.Screen>
      <Stack.Screen name="Reminder" component={ReminderScreen} options={{ title: 'Rent reminder' }} />
      <Stack.Screen name="Admin" component={AdminScreen} options={{ title: 'Admin' }} />
      <Stack.Screen name="Leads" component={LeadsScreen} options={{ title: 'Leads' }} />
      <Stack.Screen name="Buildings" component={BuildingsScreen} options={{ title: 'Buildings' }} />
    </Stack.Navigator>
  );
}

function Tabs({ user, onLogout }) {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#0b5fff',
      }}
    >
      <Tab.Screen name="BrowseTab" component={BrowseStack} options={{ title: 'Browse' }} />
      {hasPriv(user, 'view_dashboard') ? (
        <Tab.Screen name="DashTab" component={DashboardScreen} options={{ title: 'Dashboard', headerShown: true }} />
      ) : null}
      {hasPriv(user, 'manage_properties') ? (
        <Tab.Screen name="PropsTab" component={PropertyStack} options={{ title: 'Properties' }} />
      ) : null}
      {hasPriv(user, 'manage_tenants') ? (
        <Tab.Screen name="TenantsTab" component={TenantStack} options={{ title: 'Tenants' }} />
      ) : null}
      {hasPriv(user, 'view_tenant_portal') ? (
        <Tab.Screen name="PortalTab" component={PortalScreen} options={{ title: 'Portal', headerShown: true }} />
      ) : null}
      {hasPriv(user, 'view_inbox') ? (
        <Tab.Screen name="InboxTab" component={InboxScreen} options={{ title: 'Inbox', headerShown: true }} />
      ) : null}
      <Tab.Screen name="MoreTab" options={{ title: 'More' }}>
        {() => <MoreStack user={user} onLogout={onLogout} />}
      </Tab.Screen>
    </Tab.Navigator>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) {
        setReady(true);
        return;
      }
      try {
        const me = await api.me();
        setUser(me);
      } catch {
        await setToken(null);
      }
      setReady(true);
    })();
  }, []);

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: 'center' }}>
        <ActivityIndicator color="#0b5fff" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <StatusBar style="dark" />
      {user ? (
        <Tabs user={user} onLogout={() => setUser(null)} />
      ) : (
        <LoginScreen onLoggedIn={setUser} />
      )}
    </NavigationContainer>
  );
}
