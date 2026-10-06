import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { api, getApiUrl, setApiUrl, setToken } from './api';

const C = {
  bg: '#f4f6f8',
  card: '#fff',
  ink: '#111827',
  muted: '#6b7280',
  line: '#e5e7eb',
  accent: '#0b5fff',
  danger: '#dc2626',
};

export function Screen({ children }) {
  return <ScrollView style={styles.screen} contentContainerStyle={styles.pad}>{children}</ScrollView>;
}

export function Title({ children }) {
  return <Text style={styles.title}>{children}</Text>;
}

export function Card({ children }) {
  return <View style={styles.card}>{children}</View>;
}

export function Field({ label, value, onChange, placeholder, secure, keyboard }) {
  return (
    <View style={{ marginBottom: 12 }}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        secureTextEntry={secure}
        keyboardType={keyboard}
        style={styles.input}
        autoCapitalize="none"
      />
    </View>
  );
}

export function Btn({ label, onPress, tone = 'primary' }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.btn, tone === 'secondary' && styles.btnSec, tone === 'danger' && styles.btnDanger]}
    >
      <Text style={[styles.btnText, tone !== 'primary' && { color: C.ink }]}>{label}</Text>
    </Pressable>
  );
}

export function LoginScreen({ onLoggedIn }) {
  const [apiUrl, setUrl] = useState('');
  const [username, setUser] = useState('');
  const [password, setPass] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getApiUrl().then(setUrl);
  }, []);

  const submit = async () => {
    setBusy(true);
    try {
      await setApiUrl(apiUrl);
      const data = await api.login(username, password);
      await setToken(data.token);
      onLoggedIn(data.user);
    } catch (e) {
      Alert.alert('Login failed', e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Text style={styles.brand}>PropKeep</Text>
      <Text style={styles.sub}>Mobile access to the same data as the website.</Text>
      <Field
        label="Server URL"
        value={apiUrl}
        onChange={setUrl}
        placeholder="http://YOUR-LAN-IP:8000"
      />
      <Text style={styles.hint}>
        On a phone use your computer LAN IP, e.g. http://192.168.1.10:8000. Android emulator:
        http://10.0.2.2:8000
      </Text>
      <Field label="Username" value={username} onChange={setUser} />
      <Field label="Password" value={password} onChange={setPass} secure />
      {busy ? <ActivityIndicator color={C.accent} /> : <Btn label="Sign in" onPress={submit} />}
    </Screen>
  );
}

export function ListingsScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const load = () => api.listings(q).then(setRows).catch((e) => Alert.alert('Error', e.message));
  useEffect(() => {
    const u = navigation.addListener('focus', load);
    return u;
  }, [navigation, q]);
  return (
    <View style={styles.screen}>
      <View style={styles.pad}>
        <Title>Browse</Title>
        <Field placeholder="Search" value={q} onChange={setQ} />
        <Btn label="Search" onPress={load} tone="secondary" />
      </View>
      <FlatList
        data={rows}
        keyExtractor={(i) => String(i.id)}
        contentContainerStyle={styles.pad}
        renderItem={({ item }) => (
          <Pressable onPress={() => navigation.navigate('ListingDetail', { id: item.id })}>
            <Card>
              <Text style={styles.itemTitle}>{item.title}</Text>
              <Text style={styles.muted}>
                {item.city} · {item.listing_type} · {item.display_price}
              </Text>
            </Card>
          </Pressable>
        )}
      />
    </View>
  );
}

export function ListingDetailScreen({ route, user }) {
  const { id } = route.params;
  const [item, setItem] = useState(null);
  const [form, setForm] = useState({ name: '', email: '', phone: '', message: '' });
  const load = () => api.listing(id).then(setItem).catch((e) => Alert.alert('Error', e.message));
  useEffect(() => {
    load();
  }, [id]);
  if (!item) return <ActivityIndicator style={{ marginTop: 40 }} color={C.accent} />;
  return (
    <Screen>
      <Title>{item.title}</Title>
      <Text style={styles.muted}>
        {item.address}, {item.city} · {item.display_price}
      </Text>
      <Text style={styles.body}>{item.description}</Text>
      <Text style={styles.muted}>
        Rooms {item.rooms} · Kitchen {item.kitchens} · Beds {item.bedrooms}
      </Text>
      <Text style={styles.body}>{(item.amenity_labels || []).join(', ')}</Text>
      {item.can_request_join ? (
        <Btn
          label="Request owner to add me"
          onPress={() =>
            api
              .joinListing(id, 'Please add me to this vacant property.')
              .then(() => {
                Alert.alert('Sent', 'The owner will review your request.');
                load();
              })
              .catch((e) => Alert.alert('Error', e.message))
          }
        />
      ) : null}
      {item.join_request_pending ? <Text style={styles.muted}>Join request is waiting for the owner.</Text> : null}
      <Title>Enquiry</Title>
      <Field label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
      <Field label="Email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} keyboard="email-address" />
      <Field label="Phone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} />
      <Field label="Message" value={form.message} onChange={(v) => setForm({ ...form, message: v })} />
      <Btn
        label="Send enquiry"
        onPress={() =>
          api
            .enquire(id, form)
            .then(() => Alert.alert('Sent', 'The owner will contact you.'))
            .catch((e) => Alert.alert('Error', e.message))
        }
      />
    </Screen>
  );
}

export function DashboardScreen({ navigation }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    const u = navigation.addListener('focus', () =>
      api.dashboard().then(setData).catch((e) => Alert.alert('Error', e.message))
    );
    return u;
  }, [navigation]);
  if (!data) return <ActivityIndicator style={{ marginTop: 40 }} color={C.accent} />;
  return (
    <Screen>
      <Title>Dashboard</Title>
      <Card>
        <Text>Properties {data.property_count}</Text>
        <Text>
          Occupied {data.occupied} · Vacant {data.vacant}
        </Text>
        <Text>
          {data.month_label} net ₹{data.month_net}
        </Text>
      </Card>
      <Btn label="Send rent reminder" onPress={() => navigation.navigate('Reminder')} />
      <Title>Rent due</Title>
      {(data.rent_due || []).map((p) => (
        <Card key={p.id}>
          <Text style={styles.itemTitle}>{p.title}</Text>
          <Text style={styles.muted}>{p.display_price}</Text>
        </Card>
      ))}
    </Screen>
  );
}

export function PropertiesScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  const load = () => api.properties().then(setRows).catch((e) => Alert.alert('Error', e.message));
  useEffect(() => {
    const u = navigation.addListener('focus', load);
    return u;
  }, [navigation]);
  return (
    <View style={styles.screen}>
      <View style={styles.pad}>
        <Title>My properties</Title>
        <Btn label="Add property" onPress={() => navigation.navigate('PropertyForm', {})} />
      </View>
      <FlatList
        data={rows}
        keyExtractor={(i) => String(i.id)}
        contentContainerStyle={styles.pad}
        renderItem={({ item }) => (
          <Pressable onPress={() => navigation.navigate('PropertyDetail', { id: item.id })}>
            <Card>
              <Text style={styles.itemTitle}>{item.title}</Text>
              <Text style={styles.muted}>
                {item.city} · {item.is_occupied ? 'Occupied' : 'Vacant'} · {item.display_price}
              </Text>
            </Card>
          </Pressable>
        )}
      />
    </View>
  );
}

export function PropertyFormScreen({ route, navigation }) {
  const id = route.params?.id;
  const [opts, setOpts] = useState({ amenities: [], buildings: [] });
  const [form, setForm] = useState({
    title: '',
    address: '',
    city: '',
    listing_type: 'rent',
    property_type: 'apartment',
    monthly_rent: '10000',
    rooms: '2',
    kitchens: '1',
    bedrooms: '1',
    bathrooms: '1',
    amenity_ids: [],
    other_amenity: '',
    add_other: false,
    building: null,
    unit_number: '',
  });
  useEffect(() => {
    api.options().then(setOpts).catch(() => {});
    if (id) {
      api.property(id).then((p) =>
        setForm((f) => ({
          ...f,
          ...p,
          monthly_rent: String(p.monthly_rent || ''),
          rooms: String(p.rooms ?? ''),
          kitchens: String(p.kitchens ?? ''),
          bedrooms: String(p.bedrooms ?? ''),
          bathrooms: String(p.bathrooms ?? ''),
          amenity_ids: p.amenity_ids || [],
        }))
      );
    }
  }, [id]);
  const toggleAmenity = (aid) => {
    setForm((f) => ({
      ...f,
      amenity_ids: f.amenity_ids.includes(aid)
        ? f.amenity_ids.filter((x) => x !== aid)
        : [...f.amenity_ids, aid],
    }));
  };
  const save = async () => {
    const body = {
      ...form,
      monthly_rent: form.monthly_rent || null,
      rooms: Number(form.rooms || 0),
      kitchens: Number(form.kitchens || 0),
      bedrooms: Number(form.bedrooms || 1),
      bathrooms: Number(form.bathrooms || 1),
      other_amenity: form.add_other ? form.other_amenity : '',
    };
    try {
      if (id) await api.updateProperty(id, body);
      else await api.createProperty(body);
      navigation.goBack();
    } catch (e) {
      Alert.alert('Could not save', e.message);
    }
  };
  return (
    <Screen>
      <Title>{id ? 'Edit property' : 'Add property'}</Title>
      <Field label="Title" value={form.title} onChange={(v) => setForm({ ...form, title: v })} />
      <Field label="Address" value={form.address} onChange={(v) => setForm({ ...form, address: v })} />
      <Field label="City" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
      <Field label="Monthly rent" value={String(form.monthly_rent)} onChange={(v) => setForm({ ...form, monthly_rent: v })} keyboard="numeric" />
      <Field label="Rooms" value={String(form.rooms)} onChange={(v) => setForm({ ...form, rooms: v })} keyboard="numeric" />
      <Field label="Kitchens" value={String(form.kitchens)} onChange={(v) => setForm({ ...form, kitchens: v })} keyboard="numeric" />
      <Field label="Unit number" value={form.unit_number || ''} onChange={(v) => setForm({ ...form, unit_number: v })} />
      <Text style={styles.label}>Building</Text>
      {(opts.buildings || []).map((b) => (
        <Pressable key={b.id} onPress={() => setForm({ ...form, building: b.id })}>
          <Text style={{ color: form.building === b.id ? C.accent : C.ink, marginBottom: 6 }}>{b.name}</Text>
        </Pressable>
      ))}
      <Text style={styles.label}>Amenities</Text>
      {(opts.amenities || []).map((a) => (
        <View key={a.id} style={styles.row}>
          <Switch value={form.amenity_ids.includes(a.id)} onValueChange={() => toggleAmenity(a.id)} />
          <Text>{a.label}</Text>
        </View>
      ))}
      <View style={styles.row}>
        <Switch value={form.add_other} onValueChange={(v) => setForm({ ...form, add_other: v })} />
        <Text>Others</Text>
      </View>
      {form.add_other ? (
        <Field
          label="Specify other amenity"
          value={form.other_amenity}
          onChange={(v) => setForm({ ...form, other_amenity: v })}
        />
      ) : null}
      <Btn label="Save" onPress={save} />
    </Screen>
  );
}

export function PropertyDetailScreen({ route, navigation }) {
  const { id } = route.params;
  const [item, setItem] = useState(null);
  const [vacate, setVacate] = useState('');
  const load = () => api.property(id).then(setItem).catch((e) => Alert.alert('Error', e.message));
  useEffect(() => {
    const u = navigation.addListener('focus', load);
    return u;
  }, [navigation, id]);
  if (!item) return <ActivityIndicator style={{ marginTop: 40 }} color={C.accent} />;
  return (
    <Screen>
      <Title>{item.title}</Title>
      <Text style={styles.muted}>
        {item.city} · {item.is_occupied ? 'Occupied' : 'Vacant'}
      </Text>
      <Text style={styles.body}>Amenities: {(item.amenity_labels || []).join(', ') || '—'}</Text>
      <Btn label="Edit" onPress={() => navigation.navigate('PropertyForm', { id })} tone="secondary" />
      <Title>Tenants</Title>
      {(item.tenants || []).map((t) => (
        <Card key={t.id}>
          <Text style={styles.itemTitle}>{t.name}</Text>
          <Text style={styles.muted}>{t.username ? `Login: ${t.username}` : 'No login'}</Text>
        </Card>
      ))}
      <Btn label="Add tenant" onPress={() => navigation.navigate('TenantForm', { property: id })} />
      {(item.join_requests || []).map((j) => (
        <Card key={j.id}>
          <Text>{j.username} requested to join</Text>
          <Btn label="Accept" onPress={() => api.reviewJoin(j.id, 'accept').then(load)} />
          <Btn label="Decline" tone="secondary" onPress={() => api.reviewJoin(j.id, 'reject').then(load)} />
        </Card>
      ))}
      <Title>Vacate date</Title>
      <Field placeholder="YYYY-MM-DD" value={vacate} onChange={setVacate} />
      <Btn
        label="Save vacate date"
        onPress={() => api.vacate(id, vacate).then(load).catch((e) => Alert.alert('Error', e.message))}
      />
    </Screen>
  );
}

export function TenantsScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    const u = navigation.addListener('focus', () =>
      api.tenants().then(setRows).catch((e) => Alert.alert('Error', e.message))
    );
    return u;
  }, [navigation]);
  return (
    <Screen>
      <Title>Tenants</Title>
      <Btn label="Add tenant" onPress={() => navigation.navigate('TenantForm', {})} />
      {rows.map((t) => (
        <Pressable key={t.id} onPress={() => navigation.navigate('TenantForm', { id: t.id, property: t.property })}>
          <Card>
            <Text style={styles.itemTitle}>{t.name}</Text>
            <Text style={styles.muted}>
              {t.property_title} · {t.username || 'no login'}
            </Text>
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}

export function TenantFormScreen({ route, navigation }) {
  const { id, property } = route.params || {};
  const [props, setProps] = useState([]);
  const [form, setForm] = useState({
    name: '',
    phone: '',
    email: '',
    property: property || '',
    is_active: true,
    create_username: '',
    create_password: '',
    existing_username: '',
  });
  useEffect(() => {
    api.properties().then(setProps).catch(() => {});
    if (id) {
      api.tenants().then((rows) => {
        const t = rows.find((x) => x.id === id);
        if (t) setForm((f) => ({ ...f, ...t }));
      });
    }
  }, [id]);
  const save = async () => {
    try {
      if (id) await api.updateTenant(id, form);
      else await api.createTenant(form);
      navigation.goBack();
    } catch (e) {
      Alert.alert('Could not save', e.message);
    }
  };
  return (
    <Screen>
      <Title>{id ? 'Edit tenant' : 'Add tenant'}</Title>
      <Text style={styles.label}>Property</Text>
      {props.map((p) => (
        <Pressable key={p.id} onPress={() => setForm({ ...form, property: p.id })}>
          <Text style={{ color: form.property === p.id ? C.accent : C.ink, marginBottom: 6 }}>{p.title}</Text>
        </Pressable>
      ))}
      <Field label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
      <Field label="Phone" value={form.phone || ''} onChange={(v) => setForm({ ...form, phone: v })} />
      <Field label="Email" value={form.email || ''} onChange={(v) => setForm({ ...form, email: v })} />
      <Field
        label="Existing login username"
        value={form.existing_username || ''}
        onChange={(v) => setForm({ ...form, existing_username: v })}
      />
      <Field
        label="New login username"
        value={form.create_username || ''}
        onChange={(v) => setForm({ ...form, create_username: v })}
      />
      <Field
        label="New login password"
        value={form.create_password || ''}
        onChange={(v) => setForm({ ...form, create_password: v })}
        secure
      />
      <Btn label="Save tenant" onPress={save} />
    </Screen>
  );
}

export function InboxScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  const load = () => api.inbox().then(setRows).catch((e) => Alert.alert('Error', e.message));
  useEffect(() => {
    const u = navigation.addListener('focus', load);
    return u;
  }, [navigation]);
  return (
    <Screen>
      <Title>Inbox</Title>
      <Btn label="Mark all read" tone="secondary" onPress={() => api.markInbox().then(load)} />
      {rows.map((n) => (
        <Card key={n.id}>
          <Text style={styles.itemTitle}>{n.title}</Text>
          <Text style={styles.muted}>
            {n.kind_label} · {n.is_read ? 'Read' : 'New'}
          </Text>
        </Card>
      ))}
    </Screen>
  );
}

export function PortalScreen({ navigation }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    const u = navigation.addListener('focus', () =>
      api.portal().then(setData).catch((e) => Alert.alert('Error', e.message))
    );
    return u;
  }, [navigation]);
  if (!data) return <ActivityIndicator style={{ marginTop: 40 }} color={C.accent} />;
  return (
    <Screen>
      <Title>My portal</Title>
      {(data.tenants || []).map((t) => (
        <Card key={t.id}>
          <Text style={styles.itemTitle}>{t.property_title}</Text>
          <Text>{t.name}</Text>
        </Card>
      ))}
      <Title>Payments</Title>
      {(data.payments || []).map((p) => (
        <Card key={p.id}>
          <Text>
            ₹{p.amount} · {p.status}
          </Text>
        </Card>
      ))}
    </Screen>
  );
}

export function ReminderScreen({ navigation }) {
  const [tenants, setTenants] = useState([]);
  const [picked, setPicked] = useState([]);
  const [message, setMessage] = useState('Please pay this month’s rent.');
  useEffect(() => {
    api.tenants().then((rows) => {
      const active = rows.filter((t) => t.is_active);
      setTenants(active);
      setPicked(active.map((t) => t.id));
    });
  }, []);
  return (
    <Screen>
      <Title>Rent reminder</Title>
      {tenants.map((t) => (
        <View key={t.id} style={styles.row}>
          <Switch
            value={picked.includes(t.id)}
            onValueChange={() =>
              setPicked((p) => (p.includes(t.id) ? p.filter((x) => x !== t.id) : [...p, t.id]))
            }
          />
          <Text>
            {t.name} · {t.property_title}
          </Text>
        </View>
      ))}
      <Field label="Message" value={message} onChange={setMessage} />
      <Btn
        label="Send to inbox"
        onPress={() =>
          api
            .remind(picked, message)
            .then((r) => Alert.alert('Sent', `Delivered to ${r.sent} tenant inbox(es).`))
            .catch((e) => Alert.alert('Error', e.message))
        }
      />
    </Screen>
  );
}

export function AdminScreen() {
  const [audience, setAudience] = useState('all');
  const [title, setTitle] = useState('Message from admin');
  const [body, setBody] = useState('');
  return (
    <Screen>
      <Title>Message users</Title>
      {['all', 'owners', 'tenants'].map((a) => (
        <Pressable key={a} onPress={() => setAudience(a)}>
          <Text style={{ color: audience === a ? C.accent : C.ink, marginBottom: 8 }}>{a}</Text>
        </Pressable>
      ))}
      <Field label="Title" value={title} onChange={setTitle} />
      <Field label="Message" value={body} onChange={setBody} />
      <Btn
        label="Send"
        onPress={() =>
          api
            .broadcast({ audience, title, body })
            .then((r) => Alert.alert('Sent', `Delivered to ${r.sent} users.`))
            .catch((e) => Alert.alert('Error', e.message))
        }
      />
    </Screen>
  );
}

export function MoreScreen({ user, onLogout, navigation }) {
  const has = (code) => user?.is_admin || (user?.privileges || []).includes(code);
  return (
    <Screen>
      <Title>More</Title>
      <Text style={styles.muted}>
        Signed in as {user?.username} ({user?.role})
      </Text>
      {has('view_enquiries') ? (
        <Btn label="Leads" tone="secondary" onPress={() => navigation.navigate('Leads')} />
      ) : null}
      {has('view_buildings') ? (
        <Btn label="Buildings" tone="secondary" onPress={() => navigation.navigate('Buildings')} />
      ) : null}
      {has('manage_rent_reminders') ? (
        <Btn label="Rent reminder" tone="secondary" onPress={() => navigation.navigate('Reminder')} />
      ) : null}
      {user?.is_admin ? <Btn label="Admin broadcast" tone="secondary" onPress={() => navigation.navigate('Admin')} /> : null}
      <Btn
        label="Log out"
        tone="danger"
        onPress={async () => {
          try {
            await api.logout();
          } catch {}
          await setToken(null);
          onLogout();
        }}
      />
    </Screen>
  );
}

export function LeadsScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    const u = navigation.addListener('focus', () =>
      api.enquiries().then(setRows).catch((e) => Alert.alert('Error', e.message))
    );
    return u;
  }, [navigation]);
  return (
    <Screen>
      <Title>Leads</Title>
      {rows.map((e) => (
        <Card key={e.id}>
          <Text style={styles.itemTitle}>{e.name}</Text>
          <Text style={styles.muted}>
            {e.property_title} · {e.status}
          </Text>
          <Text>{e.message}</Text>
        </Card>
      ))}
    </Screen>
  );
}

export function BuildingsScreen({ navigation }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    const u = navigation.addListener('focus', () =>
      api.buildings().then(setRows).catch((e) => Alert.alert('Error', e.message))
    );
    return u;
  }, [navigation]);
  return (
    <Screen>
      <Title>Buildings</Title>
      {rows.map((b) => (
        <Card key={b.id}>
          <Text style={styles.itemTitle}>{b.name}</Text>
          <Text style={styles.muted}>
            {b.address}, {b.city}
          </Text>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  pad: { padding: 16, paddingBottom: 40 },
  brand: { fontSize: 28, fontWeight: '800', color: C.accent, marginTop: 24 },
  title: { fontSize: 22, fontWeight: '700', marginBottom: 12, color: C.ink },
  sub: { color: C.muted, marginBottom: 16 },
  hint: { color: C.muted, fontSize: 12, marginBottom: 12 },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.line,
  },
  itemTitle: { fontWeight: '700', marginBottom: 4, color: C.ink },
  muted: { color: C.muted, marginTop: 4 },
  body: { marginVertical: 8, color: C.ink },
  label: { fontWeight: '700', marginBottom: 6, color: C.ink },
  input: {
    borderWidth: 1,
    borderColor: C.line,
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  btn: { backgroundColor: C.accent, padding: 14, borderRadius: 8, alignItems: 'center', marginVertical: 6 },
  btnSec: { backgroundColor: '#e8eef7' },
  btnDanger: { backgroundColor: '#fee2e2' },
  btnText: { color: '#fff', fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
});
